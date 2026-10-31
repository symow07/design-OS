"""Protected reviewer-role lifecycle services (DIP-1A-5A).

Atomicity is proven by forcing a failure and asserting BOTH the DecisionEvent and the
role/profile change are absent; denials are proven by inspecting the audit row, not just
the exception; bootstrap closure is proven to be permanent and un-reopenable without the
gated break-glass path.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from . import authz_policy as authz
from . import role_services as RS
from .authorization import SELF_ELEVATION_FORBIDDEN
from .models import (
    GRANT_AUTHORIZED_SERVICE,
    AuthorizationAudit,
    BootstrapState,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)

pytestmark = pytest.mark.django_db
User = get_user_model()
DAY = timezone.timedelta(days=1)
_seq = 0


def _u(name, *, active=True, superuser=False):
    global _seq
    _seq += 1
    return User.objects.create_user(username=f"{name}{_seq}", password="x",
                                    is_active=active, is_superuser=superuser)


def actor(role=authz.BRAND_ADMIN):
    """An authorized acting reviewer (BRAND_ADMIN may grant/revoke/enable/disable)."""
    u = _u("actor")
    ReviewerProfile.objects.create(user=u, reviewer_enabled=True)
    g = _u("actorgranter")
    ReviewerRoleAssignment(
        user=u, role=role, granted_at=timezone.now(), expires_at=timezone.now() + 30 * DAY,
        grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=g, grant_reason="seed").save()
    return u


def target(*, enabled=True):
    u = _u("target")
    ReviewerProfile.objects.create(user=u, reviewer_enabled=enabled)
    return u


def _future():
    return timezone.now() + 30 * DAY


# === grant ========================================================================
def test_grant_creates_assignment_event_audit_and_closes_bootstrap():
    a, t = actor(), target()
    ev, assign = RS.grant_reviewer_role(
        actor=a, target_user=t, role=authz.DESIGN_REVIEWER, expires_at=_future(),
        reason="onboarding")
    assert ev.action == authz.GRANT_REVIEWER_ROLE and ev.actor_id == a.pk
    assert ev.role_used == authz.BRAND_ADMIN            # derived, not caller-supplied
    assert assign.role == authz.DESIGN_REVIEWER and assign.user_id == t.pk
    assert assign.grant_source == GRANT_AUTHORIZED_SERVICE and assign.granted_by_id == a.pk
    assert AuthorizationAudit.objects.filter(result="ALLOWED",
                                             action=authz.GRANT_REVIEWER_ROLE).exists()
    assert BootstrapState.objects.get(pk=1).closed is True   # first protected event closes


def test_grant_signed_payload_carries_target_role_and_snapshot():
    a, t = actor(), target()
    ev, _ = RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                                   expires_at=_future(), reason="r")
    p = ev.payload
    assert p["target_user_id"] == t.pk and p["role"] == authz.DESIGN_REVIEWER
    assert p["authz_snapshot"]["role_used"] == authz.BRAND_ADMIN
    assert p["authz_snapshot"]["policy_version"] == authz.POLICY_VERSION


def test_grant_service_has_no_role_used_parameter():
    import inspect
    params = set(inspect.signature(RS.grant_reviewer_role).parameters)
    assert "role_used" not in params and "authorization" not in params


# === atomicity: event and assignment commit together ============================
def test_forced_event_failure_rolls_back_the_grant(monkeypatch):
    a, t = actor(), target()
    monkeypatch.setattr(RS, "append_decision",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("append down")))
    with pytest.raises(RuntimeError):
        RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                               expires_at=_future(), reason="r")
    assert DecisionEvent.objects.count() == 0
    assert not ReviewerRoleAssignment.objects.filter(user=t).exists()


def test_forced_audit_failure_rolls_back_event_and_assignment(monkeypatch):
    a, t = actor(), target()
    monkeypatch.setattr(RS, "record_authorization",
                        lambda *a_, **k: (_ for _ in ()).throw(RuntimeError("audit down")))
    with pytest.raises(RuntimeError):
        RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                               expires_at=_future(), reason="r")
    assert DecisionEvent.objects.count() == 0                  # event rolled back
    assert not ReviewerRoleAssignment.objects.filter(user=t).exists()   # and assignment


# === denials (audited outside the rolled-back txn) ==============================
def test_unauthorized_grant_is_denied_and_audited():
    a = actor(role=authz.OBSERVER)          # OBSERVER may not grant
    t = target()
    with pytest.raises(RS.RoleServiceDenied):
        RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                               expires_at=_future(), reason="r")
    row = AuthorizationAudit.objects.get(result="DENIED",
                                         action=authz.GRANT_REVIEWER_ROLE)
    assert row.user_id == a.pk
    assert DecisionEvent.objects.count() == 0


def test_self_elevation_is_denied_and_audited():
    a = actor(role=authz.BRAND_ADMIN)
    ReviewerProfile.objects.filter(user=a).update(reviewer_enabled=True)
    with pytest.raises(RS.RoleServiceDenied):
        RS.grant_reviewer_role(actor=a, target_user=a, role=authz.BUSINESS_OWNER,
                               expires_at=_future(), reason="promote me")
    row = AuthorizationAudit.objects.get(reason_code=SELF_ELEVATION_FORBIDDEN)
    assert row.user_id == a.pk and row.result == "DENIED"
    assert not ReviewerRoleAssignment.objects.filter(user=a,
                                                     role=authz.BUSINESS_OWNER).exists()


def test_grant_to_target_without_enabled_profile_is_refused():
    a, t = actor(), target(enabled=False)
    with pytest.raises(RS.RoleServiceError):
        RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                               expires_at=_future(), reason="r")


def test_overlapping_active_grant_is_rejected():
    a, t = actor(), target()
    RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                           expires_at=_future(), reason="first")
    with pytest.raises(RS.RoleServiceError):
        RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                               expires_at=_future(), reason="second")
    assert ReviewerRoleAssignment.objects.filter(user=t,
                                                 role=authz.DESIGN_REVIEWER).count() == 1


# === revoke =======================================================================
def test_revoke_is_immediate_and_append_only():
    a, t = actor(), target()
    _, assign = RS.grant_reviewer_role(actor=a, target_user=t,
                                       role=authz.DESIGN_REVIEWER, expires_at=_future(),
                                       reason="r")
    ev, revoked = RS.revoke_reviewer_role(actor=a, assignment=assign, reason="left")
    assert ev.action == authz.REVOKE_REVIEWER_ROLE
    revoked.refresh_from_db()
    assert revoked.revoked_at is not None and revoked.revoked_by_id == a.pk
    assert revoked.pk == assign.pk                      # same row, not deleted
    from .models import active_roles
    assert authz.DESIGN_REVIEWER not in active_roles(t)   # immediate


def test_repeated_identical_revocation_is_idempotent():
    a, t = actor(), target()
    _, assign = RS.grant_reviewer_role(actor=a, target_user=t,
                                       role=authz.DESIGN_REVIEWER, expires_at=_future(),
                                       reason="r")
    RS.revoke_reviewer_role(actor=a, assignment=assign, reason="left")
    n_events = DecisionEvent.objects.count()
    ev2, _ = RS.revoke_reviewer_role(actor=a, assignment=assign, reason="left")
    assert ev2 is None                                  # no second event
    assert DecisionEvent.objects.count() == n_events    # idempotent


def test_conflicting_revocation_fails_closed():
    a, t = actor(), target()
    a2 = actor(role=authz.BRAND_ADMIN)
    _, assign = RS.grant_reviewer_role(actor=a, target_user=t,
                                       role=authz.DESIGN_REVIEWER, expires_at=_future(),
                                       reason="r")
    RS.revoke_reviewer_role(actor=a, assignment=assign, reason="left")
    with pytest.raises(RS.RevocationConflict):
        RS.revoke_reviewer_role(actor=a2, assignment=assign, reason="different reason")


# === enable / disable =============================================================
def test_enable_then_disable_profile():
    a = actor()
    t = _u("bare")                                      # no profile yet
    ev1, prof = RS.enable_reviewer_profile(actor=a, target_user=t, reason="onboard")
    assert ev1.action == authz.ENABLE_REVIEWER_PROFILE and prof.reviewer_enabled is True
    ev2, prof2 = RS.disable_reviewer_profile(actor=a, target_user=t, reason="offboard")
    assert ev2.action == authz.DISABLE_REVIEWER_PROFILE and prof2.reviewer_enabled is False


def test_enable_already_enabled_is_idempotent_noop():
    a, t = actor(), target(enabled=True)
    ev, _ = RS.enable_reviewer_profile(actor=a, target_user=t, reason="again")
    assert ev is None                                   # no event for a no-op


# === bootstrap lifecycle ==========================================================
@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_seeds_only_under_initial_conditions():
    from django.core.management import call_command
    op = _u("root", superuser=True)
    u = _u("firstreviewer")
    call_command("bootstrap_reviewer_role", "--username", u.username,
                 "--role", authz.BRAND_ADMIN, "--expires-days", "30",
                 "--reason", "founding", "--superuser", op.username, "--yes")
    assert ReviewerRoleAssignment.objects.filter(user=u, role=authz.BRAND_ADMIN).exists()
    assert BootstrapState.objects.get(pk=1).closed is False   # command records no event


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_requires_active_superuser_operator():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    notsuper = _u("notroot", superuser=False)
    u = _u("cand")
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", "--username", u.username,
                     "--role", authz.BRAND_ADMIN, "--expires-days", "30",
                     "--reason", "x", "--superuser", notsuper.username, "--yes")


@override_settings(BOOTSTRAP_ENABLED=False)
def test_bootstrap_refuses_when_flag_disabled():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    op = _u("root", superuser=True)
    u = _u("cand")
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", "--username", u.username,
                     "--role", authz.BRAND_ADMIN, "--expires-days", "30",
                     "--reason", "x", "--superuser", op.username, "--yes")


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_closes_after_first_protected_grant_and_will_not_reopen():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    # a protected grant closes bootstrap
    a, t = actor(), target()
    RS.grant_reviewer_role(actor=a, target_user=t, role=authz.DESIGN_REVIEWER,
                           expires_at=_future(), reason="r")
    assert BootstrapState.objects.get(pk=1).closed is True
    # bootstrap now refuses
    op = _u("root", superuser=True)
    u = _u("cand")
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", "--username", u.username,
                     "--role", authz.BRAND_ADMIN, "--expires-days", "30",
                     "--reason", "x", "--superuser", op.username, "--yes")


@override_settings(BOOTSTRAP_BREAK_GLASS_ENABLED=False)
def test_break_glass_refuses_without_its_own_flag():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    op = _u("root", superuser=True)
    BootstrapState.objects.filter(pk=1).update(closed=True)
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", "--break-glass", "--superuser",
                     op.username)
    assert BootstrapState.objects.get(pk=1).closed is True     # not reopened


@override_settings(BOOTSTRAP_BREAK_GLASS_ENABLED=True)
def test_break_glass_reopens_with_critical_audit_and_grants_nothing():
    from django.core.management import call_command
    op = _u("root", superuser=True)
    BootstrapState.objects.filter(pk=1).update(closed=True)
    before = ReviewerRoleAssignment.objects.count()
    call_command("bootstrap_reviewer_role", "--break-glass", "--superuser", op.username)
    state = BootstrapState.objects.get(pk=1)
    assert state.closed is False and state.break_glass_count == 1
    assert ReviewerRoleAssignment.objects.count() == before    # granted nothing
    audit = AuthorizationAudit.objects.get(reason_code="BOOTSTRAP_BREAK_GLASS_REOPEN")
    assert audit.metadata["severity"] == "CRITICAL" and audit.user_id == op.pk


# === still-absent gates ===========================================================
def test_no_approval_permission_retrieval_or_activation_surface():
    import apps.accounts.role_services as mod
    text = open(mod.__file__).read()
    for forbidden in ("retrieval", "automatic_use", "grant_permission(", "approve_license",
                      "activate", "confirm_ownership"):
        assert forbidden not in text, f"1A-5A must not introduce {forbidden!r}"
