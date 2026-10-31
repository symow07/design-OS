"""Reviewer identity, role resolution, constraints and bootstrap (DIP-1A-2).

The load-bearing property is the resolver: `active_roles` must fail closed on every axis,
and must answer the *point-in-time* question honestly (a since-revoked role WAS active
before its revocation). The database constraints are the second line — they refuse
malformed history that a buggy service layer might otherwise write.
"""
from __future__ import annotations

import datetime as dt
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from . import authz_policy as authz
from .models import (
    GRANT_AUTHORIZED_SERVICE,
    GRANT_BOOTSTRAP,
    GRANT_TEST_FIXTURE,
    ReviewerProfile,
    ReviewerRoleAssignment,
    active_roles,
    overlapping_active_assignments,
)

pytestmark = pytest.mark.django_db
User = get_user_model()

ROLE = authz.DESIGN_REVIEWER
OTHER_ROLE = authz.LEGAL_REVIEWER
DAY = dt.timedelta(days=1)


# --- helpers ---------------------------------------------------------------------
def make_user(username="alice", *, is_active=True, enabled=True, profile=True):
    user = User.objects.create_user(username=username, password="x", is_active=is_active)
    if profile:
        ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    return user


_granter_seq = 0


def grant(user, role=ROLE, *, granted_at=None, expires_at=None, revoked_at=None,
          revoked_by=None, source=GRANT_AUTHORIZED_SERVICE, granted_by=None,
          reason="because", revocation_reason=""):
    global _granter_seq
    now = timezone.now()
    granted_at = granted_at or now
    expires_at = expires_at or (now + 30 * DAY)
    if granted_by is None and source != GRANT_BOOTSTRAP:
        _granter_seq += 1
        granted_by = User.objects.create_user(username=f"granter-{_granter_seq}",
                                               password="x")
    a = ReviewerRoleAssignment(
        user=user, role=role, granted_at=granted_at, expires_at=expires_at,
        revoked_at=revoked_at, revoked_by=revoked_by, grant_source=source,
        granted_by=granted_by, grant_reason=reason, revocation_reason=revocation_reason)
    a.save()
    return a


# === resolver: fail-closed axes ==================================================
def test_active_role_is_resolved_for_a_healthy_grant():
    user = make_user()
    grant(user)
    assert active_roles(user) == (ROLE,)


def test_none_user_has_no_roles():
    assert active_roles(None) == ()


def test_anonymous_user_has_no_roles():
    from django.contrib.auth.models import AnonymousUser
    assert active_roles(AnonymousUser()) == ()


def test_inactive_user_has_no_roles():
    user = make_user(is_active=False)
    grant(user)
    assert active_roles(user) == ()


def test_user_without_profile_has_no_roles():
    user = make_user(profile=False)
    grant(user)
    assert active_roles(user) == ()


def test_user_with_disabled_profile_has_no_roles():
    user = make_user(enabled=False)
    grant(user)
    assert active_roles(user) == ()


def test_expired_grant_is_not_active():
    user = make_user()
    grant(user, granted_at=timezone.now() - 10 * DAY,
          expires_at=timezone.now() - DAY)
    assert active_roles(user) == ()


def test_future_grant_is_not_yet_active():
    user = make_user()
    grant(user, granted_at=timezone.now() + DAY, expires_at=timezone.now() + 30 * DAY)
    assert active_roles(user) == ()


def test_revoked_grant_is_not_active_now():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    grant(user, granted_at=timezone.now() - 5 * DAY,
          revoked_at=timezone.now() - DAY, revoked_by=granter,
          revocation_reason="left the team")
    assert active_roles(user) == ()


def test_a_role_no_longer_in_policy_grants_nothing():
    user = make_user()
    # write a row with a role that is not in authz.ROLES, bypassing full_clean
    now = timezone.now()
    granter = User.objects.create_user(username="g", password="x")
    ReviewerRoleAssignment.objects.bulk_create([ReviewerRoleAssignment(
        user=user, role="RETIRED_ROLE", granted_at=now, expires_at=now + 30 * DAY,
        grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=granter,
        grant_reason="legacy")])
    assert active_roles(user) == ()


# === resolver: point-in-time semantics ===========================================
def test_revoked_role_was_active_before_its_revocation():
    """The whole 'who could do this, and when?' premise: history is honest."""
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    t0 = timezone.now() - 10 * DAY
    revoked = timezone.now() - 2 * DAY
    grant(user, granted_at=t0, expires_at=timezone.now() + 30 * DAY,
          revoked_at=revoked, revoked_by=granter, revocation_reason="rotation")

    # before revocation: active
    assert active_roles(user, at=t0 + DAY) == (ROLE,)
    # exactly at revocation and after: not active
    assert active_roles(user, at=revoked) == ()
    assert active_roles(user, at=revoked + DAY) == ()


def test_at_defaults_to_now():
    user = make_user()
    grant(user)
    assert active_roles(user, at=None) == active_roles(user)


# === resolver: multiple + overlapping ============================================
def test_multiple_distinct_roles_are_all_returned_sorted():
    user = make_user()
    grant(user, role=ROLE)
    grant(user, role=OTHER_ROLE)
    assert active_roles(user) == tuple(sorted((ROLE, OTHER_ROLE)))


def test_overlapping_grants_of_one_role_collapse_to_one_authority():
    user = make_user()
    grant(user, role=ROLE)
    grant(user, role=ROLE)
    assert active_roles(user) == (ROLE,)
    assert overlapping_active_assignments(user) == {ROLE: 2}


def test_overlapping_diagnostics_empty_when_no_overlap():
    user = make_user()
    grant(user, role=ROLE)
    assert overlapping_active_assignments(user) == {}


# === model validation ============================================================
def test_invalid_role_is_refused_by_clean():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    a = ReviewerRoleAssignment(
        user=user, role="NOPE", granted_at=timezone.now(),
        expires_at=timezone.now() + DAY, grant_source=GRANT_AUTHORIZED_SERVICE,
        granted_by=granter, grant_reason="x")
    with pytest.raises(ValidationError):
        a.save()


def test_expiry_before_grant_is_refused():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    a = ReviewerRoleAssignment(
        user=user, role=ROLE, granted_at=timezone.now(),
        expires_at=timezone.now() - DAY, grant_source=GRANT_AUTHORIZED_SERVICE,
        granted_by=granter, grant_reason="x")
    with pytest.raises(ValidationError):
        a.save()


def test_non_bootstrap_grant_without_granter_is_refused():
    user = make_user()
    a = ReviewerRoleAssignment(
        user=user, role=ROLE, granted_at=timezone.now(),
        expires_at=timezone.now() + DAY, grant_source=GRANT_AUTHORIZED_SERVICE,
        granted_by=None, grant_reason="x")
    with pytest.raises(ValidationError):
        a.save()


def test_blank_grant_reason_is_refused():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    a = ReviewerRoleAssignment(
        user=user, role=ROLE, granted_at=timezone.now(),
        expires_at=timezone.now() + DAY, grant_source=GRANT_AUTHORIZED_SERVICE,
        granted_by=granter, grant_reason="   ")
    with pytest.raises(ValidationError):
        a.save()


def test_revocation_without_revoker_is_refused():
    user = make_user()
    a = grant(user)
    a.revoked_at = timezone.now()
    a.revoked_by = None
    with pytest.raises(ValidationError):
        a.save()


def test_future_revocation_is_refused():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    a = grant(user)
    a.revoked_at = timezone.now() + DAY
    a.revoked_by = granter
    a.revocation_reason = "scheduled?"
    with pytest.raises(ValidationError):
        a.save()


def test_production_revocation_requires_reason():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    a = grant(user, source=GRANT_AUTHORIZED_SERVICE)
    a.revoked_at = timezone.now()
    a.revoked_by = granter
    a.revocation_reason = ""
    with pytest.raises(ValidationError):
        a.save()


def test_test_fixture_revocation_may_omit_reason():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    a = grant(user, source=GRANT_TEST_FIXTURE)
    a.revoked_at = timezone.now()
    a.revoked_by = granter
    a.revocation_reason = ""
    a.save()  # must not raise
    assert active_roles(user) == ()


# === database constraints (defeat a clean() bypass) ==============================
def test_db_refuses_expiry_before_grant_even_bypassing_clean():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    now = timezone.now()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReviewerRoleAssignment.objects.bulk_create([ReviewerRoleAssignment(
                user=user, role=ROLE, granted_at=now, expires_at=now - DAY,
                grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=granter,
                grant_reason="x")])


def test_db_refuses_revocation_without_revoker_even_bypassing_clean():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    now = timezone.now()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReviewerRoleAssignment.objects.bulk_create([ReviewerRoleAssignment(
                user=user, role=ROLE, granted_at=now - DAY, expires_at=now + DAY,
                revoked_at=now, revoked_by=None,
                grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=granter,
                grant_reason="x")])


def test_db_refuses_non_bootstrap_grant_without_granter_even_bypassing_clean():
    user = make_user()
    now = timezone.now()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReviewerRoleAssignment.objects.bulk_create([ReviewerRoleAssignment(
                user=user, role=ROLE, granted_at=now, expires_at=now + DAY,
                grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=None,
                grant_reason="x")])


def test_db_allows_bootstrap_grant_without_granter():
    user = make_user()
    now = timezone.now()
    ReviewerRoleAssignment.objects.bulk_create([ReviewerRoleAssignment(
        user=user, role=ROLE, granted_at=now, expires_at=now + DAY,
        grant_source=GRANT_BOOTSTRAP, granted_by=None, grant_reason="seed")])
    assert active_roles(user) == (ROLE,)


# === PROTECT: user deletion cannot erase history =================================
def test_user_with_assignment_cannot_be_deleted():
    user = make_user()
    grant(user)
    from django.db.models import ProtectedError
    with pytest.raises(ProtectedError):
        user.delete()


def test_granter_cannot_be_deleted_while_named_on_a_grant():
    user = make_user()
    granter = User.objects.create_user(username="g", password="x")
    grant(user, granted_by=granter)
    from django.db.models import ProtectedError
    with pytest.raises(ProtectedError):
        granter.delete()


# === bootstrap management command (1A-2 seeding, gated by 1A-5A) =================
# 1A-5A made bootstrap deployment-gated (BOOTSTRAP_ENABLED) and operator-gated (a named
# active superuser). These tests supply both so they exercise the SEEDING behaviour, not
# the gate (the gate itself is covered in test_role_services.py).
def _su():
    return User.objects.create_user(username="rootop", password="x", is_superuser=True)


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_command_seeds_profile_and_assignment():
    """Legacy two-person bootstrap, unchanged — but no longer for DESIGN_REVIEWER (see
    test_bootstrap_command_refuses_direct_design_reviewer). BRAND_ADMIN is the role this
    path legitimately seeds: it can then use the protected role service, which records a
    DecisionEvent and closes bootstrap."""
    su = _su()
    User.objects.create_user(username="carol", password="x")
    out = StringIO()
    call_command("bootstrap_reviewer_role", "--username=carol",
                 f"--role={authz.BRAND_ADMIN}",
                 "--expires-days=30", "--reason=founding reviewer",
                 "--superuser", su.username, "--yes", stdout=out)
    user = User.objects.get(username="carol")
    assert user.reviewer_profile.reviewer_enabled is True
    assert active_roles(user) == (authz.BRAND_ADMIN,)
    a = ReviewerRoleAssignment.objects.get(user=user, role=authz.BRAND_ADMIN)
    assert a.grant_source == GRANT_BOOTSTRAP and a.granted_by_id is None


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_command_refuses_direct_design_reviewer():
    """DIP-1A-BOOTSTRAP-CORR-2: the direct DESIGN_REVIEWER path is closed because it left
    BootstrapState open forever. The error must name the replacement, not just refuse."""
    su = _su()
    User.objects.create_user(username="dana", password="x")
    with pytest.raises(CommandError) as exc:
        call_command("bootstrap_reviewer_role", "--username=dana", f"--role={ROLE}",
                     "--expires-days=30", "--reason=x", "--superuser", su.username,
                     "--yes")
    assert "bootstrap_single_operator_reviewer" in str(exc.value)
    assert not ReviewerRoleAssignment.objects.filter(role=ROLE).exists()


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_command_refuses_unknown_user():
    su = _su()
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", "--username=ghost", f"--role={ROLE}",
                     "--expires-days=30", "--reason=x", "--superuser", su.username, "--yes")


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_command_refuses_invalid_role():
    su = _su()
    User.objects.create_user(username="dave", password="x")
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", "--username=dave", "--role=NOPE",
                     "--expires-days=30", "--reason=x", "--superuser", su.username, "--yes")


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_command_refuses_duplicate_active_grant():
    su = _su()
    User.objects.create_user(username="erin", password="x")
    args = ("--username=erin", f"--role={authz.BRAND_ADMIN}", "--expires-days=30",
            "--reason=x", "--superuser", su.username, "--yes")
    call_command("bootstrap_reviewer_role", *args)
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", *args)


@override_settings(BOOTSTRAP_ENABLED=True)
def test_bootstrap_command_refuses_inactive_user():
    su = _su()
    User.objects.create_user(username="frank", password="x", is_active=False)
    with pytest.raises(CommandError):
        call_command("bootstrap_reviewer_role", "--username=frank", f"--role={ROLE}",
                     "--expires-days=30", "--reason=x", "--superuser", su.username, "--yes")


# === policy check ================================================================
def test_authz_policy_check_passes_with_real_policy():
    from .checks import check_authz_policy_source
    assert check_authz_policy_source(None) == []
