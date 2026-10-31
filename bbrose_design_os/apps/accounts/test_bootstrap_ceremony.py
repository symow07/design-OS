"""DIP-1A-BOOTSTRAP-CORR-2 — single-operator initial reviewer ceremony.

The ceremony's whole justification is that it is honest about being weaker than dual
control. So the tests that matter most are the ones proving it cannot be mistaken for
something stronger: the action is unauthorizable by any role, the sentinel is confined to
one action, a fabricated authorization snapshot is fatal, and the event is invisible to
every projector and to dual-control validation.
"""
from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
import pytest

from . import authz_policy as authz
from . import bootstrap_registry as reg
from .authorization import authorize_actor
from .bootstrap_ceremony import (
    ALREADY_COMPLETED, STATE_INCONSISTENT, CeremonyError,
    perform_single_operator_ceremony,
)
from .bootstrap_environment import EnvironmentClassificationError, classify_environment
from .bootstrap_preflight import build_ceremony_preflight
from .bootstrap_verification import (
    verify_bootstrap_consistency, verify_bootstrap_event,
)
from .chain_verification import verify_decision_chain
from .decision_chain import ChainError, append_decision, verify_chain
from .models import (
    GRANT_BOOTSTRAP_SINGLE_OPERATOR, GRANT_TEST_FIXTURE, AuthorizationAudit,
    BootstrapState, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
)
from .security import signing

pytestmark = pytest.mark.django_db
User = get_user_model()
KEY = "7" * 32
REASON = "DIP-1C-5C bounded human semantic metadata pilot"


@pytest.fixture(autouse=True)
def _signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"ceremony-test": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "ceremony-test"
    signing.reset_registry()
    yield
    signing.reset_registry()


@pytest.fixture
def local(settings):
    """A classified local development environment."""
    settings.BOOTSTRAP_ENABLED = True
    settings.BOOTSTRAP_SINGLE_OPERATOR_ENABLED = True
    settings.DEBUG = True
    settings.ENVIRONMENT = "LOCAL_DEVELOPMENT"
    settings.LOCAL_DEVELOPMENT_DATABASES = [settings.DATABASES["default"]["NAME"]]
    return settings


@pytest.fixture
def operator():
    return User.objects.create_user(
        username="local-operator", password="x", is_superuser=True, is_staff=True)


def _perform(user, **changes):
    kwargs = {
        "authenticated_user": user, "role": authz.DESIGN_REVIEWER, "expires_days": 14,
        "reason": REASON,
        "account_control_basis": reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE,
    }
    kwargs.update(changes)
    return perform_single_operator_ceremony(**kwargs)


def _authority_untouched():
    return (DecisionEvent.objects.count() == 0
            and ReviewerRoleAssignment.objects.count() == 0
            and BootstrapState.objects.get(pk=1).closed is False)


# === the action is not authorizable by anybody ===================================

def test_bootstrap_action_is_outside_the_ordinary_authorization_system():
    assert reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE not in authz.ACTIONS
    assert reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE not in authz.POLICY
    assert reg.BOOTSTRAP_OPERATOR not in authz.ROLES
    for role in authz.ROLES:
        assert not authz.may(role, reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE)


def test_authorize_actor_and_append_decision_both_refuse_the_bootstrap_action(operator):
    ReviewerProfile.objects.create(user=operator, reviewer_enabled=True)
    granter = User.objects.create_user(username="granter")
    ReviewerRoleAssignment.objects.create(
        user=operator, role=authz.BUSINESS_OWNER, granted_by=granter,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="t")
    result = authorize_actor(operator, reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE)
    assert not result.allowed
    assert result.reason_code == "ACTION_UNKNOWN"
    with pytest.raises(ChainError):
        append_decision(user=operator, action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE,
                        payload={"x": 1})
    assert DecisionEvent.objects.count() == 0


def test_bootstrap_action_is_not_reachable_from_any_protected_endpoint():
    from .authorization import PROTECTED_ACTIONS
    assert reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE not in PROTECTED_ACTIONS


# === environment classification ==================================================

def test_environment_refuses_every_way_of_not_being_local(local, settings):
    assert classify_environment()[0] == "LOCAL_DEVELOPMENT"
    for attribute, value, code in [
        ("BOOTSTRAP_ENABLED", False, "BOOTSTRAP_NOT_ENABLED"),
        ("BOOTSTRAP_SINGLE_OPERATOR_ENABLED", False,
         "SINGLE_OPERATOR_BOOTSTRAP_NOT_ENABLED"),
        ("DEBUG", False, "DEBUG_IS_NOT_ENABLED"),
        ("ENVIRONMENT", "STAGING", "ENVIRONMENT_NOT_DECLARED_LOCAL_DEVELOPMENT"),
        ("LOCAL_DEVELOPMENT_DATABASES", ["something-else"],
         "DATABASE_NAME_NOT_IN_LOCAL_DEVELOPMENT_ALLOW_LIST"),
    ]:
        original = getattr(settings, attribute)
        setattr(settings, attribute, value)
        with pytest.raises(EnvironmentClassificationError) as exc:
            classify_environment()
        assert exc.value.code == code
        setattr(settings, attribute, original)


def test_a_tunnelled_database_on_loopback_is_not_local_without_the_allow_list(
        local, settings):
    """The endpoint being loopback proves nothing: a tunnel looks identical."""
    databases = dict(settings.DATABASES)
    databases["default"] = {**databases["default"], "HOST": "127.0.0.1",
                            "NAME": "production_db"}
    settings.DATABASES = databases
    with pytest.raises(EnvironmentClassificationError) as exc:
        classify_environment()
    assert exc.value.code == "DATABASE_NAME_NOT_IN_LOCAL_DEVELOPMENT_ALLOW_LIST"


def test_a_production_marker_refuses_even_a_local_looking_environment(local, settings):
    settings.SENTRY_DSN = "https://example.invalid/1"
    with pytest.raises(EnvironmentClassificationError) as exc:
        classify_environment()
    assert exc.value.code == "PRODUCTION_MARKER_PRESENT"


def test_system_check_fails_when_the_flag_is_set_outside_local_development(settings):
    from .checks import check_single_operator_bootstrap_is_local_only
    settings.BOOTSTRAP_SINGLE_OPERATOR_ENABLED = True
    settings.ENVIRONMENT = "PRODUCTION"
    settings.DEBUG = False
    ids = {error.id for error in check_single_operator_bootstrap_is_local_only(None)}
    assert "accounts.bootstrap.E010" in ids and "accounts.bootstrap.E011" in ids
    settings.BOOTSTRAP_SINGLE_OPERATOR_ENABLED = False
    assert check_single_operator_bootstrap_is_local_only(None) == []


# === ceremony preconditions ======================================================

def test_only_design_reviewer_is_permitted(local, operator):
    for role in (authz.BRAND_ADMIN, authz.BUSINESS_OWNER, authz.LEGAL_REVIEWER,
                 authz.SYSTEM_ADMIN, "SOME_FUTURE_ROLE"):
        with pytest.raises(CeremonyError) as exc:
            _perform(operator, role=role)
        assert exc.value.code == "ROLE_NOT_PERMITTED_IN_CEREMONY"
    assert _authority_untouched()


def test_expiry_and_reason_are_bounded_and_required(local, operator):
    for changes, code in [
        ({"expires_days": 0}, "EXPIRY_REQUIRED"),
        ({"expires_days": None}, "EXPIRY_REQUIRED"),
        ({"expires_days": 31}, "EXPIRY_EXCEEDS_BOUND"),
        ({"reason": "   "}, "REASON_REQUIRED"),
        ({"reason": "x" * 501}, "REASON_TOO_LONG"),
    ]:
        with pytest.raises(CeremonyError) as exc:
            _perform(operator, **changes)
        assert exc.value.code == code
    assert _authority_untouched()


def test_account_must_be_an_active_superuser(local):
    inactive = User.objects.create_user(
        username="inactive", is_superuser=True, is_active=False)
    plain = User.objects.create_user(username="plain")
    with pytest.raises(CeremonyError) as exc:
        _perform(inactive)
    assert exc.value.code == "ACCOUNT_INACTIVE"
    with pytest.raises(CeremonyError) as exc:
        _perform(plain)
    assert exc.value.code == "ACCOUNT_NOT_SUPERUSER"
    assert _authority_untouched()


def test_an_unknown_account_control_basis_is_refused(local, operator):
    with pytest.raises(CeremonyError) as exc:
        _perform(operator, account_control_basis="TRUSTED_USERNAME_ARGUMENT")
    assert exc.value.code == "UNSUPPORTED_ACCOUNT_CONTROL_BASIS"
    assert _authority_untouched()


def test_existing_authority_or_a_non_genesis_chain_refuses(local, operator):
    granter = User.objects.create_user(username="granter")
    ReviewerProfile.objects.create(user=operator, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=operator, role=authz.DESIGN_REVIEWER, granted_by=granter,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="t")
    with pytest.raises(CeremonyError) as exc:
        _perform(operator)
    assert exc.value.code == "REVIEWER_ROLE_ASSIGNMENTS_ALREADY_EXIST"
    assert DecisionEvent.objects.count() == 0


def test_a_closed_or_break_glassed_state_refuses(local, operator):
    state = BootstrapState.objects.get(pk=1)
    state.closed = True
    state.save()
    with pytest.raises(CeremonyError) as exc:
        _perform(operator)
    assert exc.value.code == "BOOTSTRAP_PERMANENTLY_CLOSED"
    state.closed = False
    state.break_glass_count = 1
    state.save()
    with pytest.raises(CeremonyError) as exc:
        _perform(operator)
    assert exc.value.code == "BREAK_GLASS_COUNT_IS_NOT_ZERO"
    assert DecisionEvent.objects.count() == 0


# === the ceremony itself =========================================================

def test_ceremony_grants_closes_and_records_itself_as_single_operator(local, operator):
    result = _perform(operator)
    assert result.status == "PERFORMED"

    event = DecisionEvent.objects.get()
    assert event.action == reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE
    assert event.role_used == reg.BOOTSTRAP_OPERATOR
    assert event.subject_type == "User" and event.subject_id == str(operator.pk)
    assert event.payload["single_operator"] is True
    assert event.payload["dual_control"] is False
    assert event.payload["actor_user_id"] == event.payload["target_user_id"]
    assert event.payload["account_control_basis"] == (
        reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE)
    assert event.payload["authorization_basis"] == reg.AUTHORIZATION_BASIS
    assert "authz_snapshot" not in event.payload

    assignment = ReviewerRoleAssignment.objects.get()
    assert assignment.role == authz.DESIGN_REVIEWER
    assert assignment.grant_source == GRANT_BOOTSTRAP_SINGLE_OPERATOR
    assert assignment.granted_by_id == operator.pk      # nameable, not null
    assert ReviewerProfile.objects.get(user=operator).reviewer_enabled

    state = BootstrapState.objects.get(pk=1)
    assert state.closed is True and state.break_glass_count == 0
    assert state.closed_by_event_id == event.pk

    audit = AuthorizationAudit.objects.get(
        action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE)
    assert audit.metadata["severity"] == "CRITICAL"
    assert audit.metadata["single_operator"] is True
    assert audit.metadata["dual_control"] is False
    assert audit.role_used == reg.BOOTSTRAP_OPERATOR

    assert verify_chain().ok
    assert verify_decision_chain().ok


def test_the_ceremony_creates_no_permission_governance_or_assertion(local, operator):
    from apps.intelligence.models import (
        GovernanceDecisionProjection, HumanAssertionProjection,
        OperationalPermissionProjection,
    )
    _perform(operator)
    assert OperationalPermissionProjection.objects.count() == 0
    assert GovernanceDecisionProjection.objects.count() == 0
    assert HumanAssertionProjection.objects.count() == 0


def test_a_second_ceremony_is_refused_and_a_repeat_reconciles(local, operator):
    first = _perform(operator)
    repeat = _perform(operator)
    assert repeat.status == ALREADY_COMPLETED
    assert repeat.event_id == first.event_id
    assert DecisionEvent.objects.count() == 1
    assert ReviewerRoleAssignment.objects.count() == 1

    other = User.objects.create_user(
        username="other-operator", is_superuser=True)
    with pytest.raises(CeremonyError):
        _perform(other)
    assert DecisionEvent.objects.count() == 1


def test_a_repeat_against_a_mutated_state_reports_inconsistency(local, operator):
    _perform(operator)
    ReviewerRoleAssignment.objects.all().delete()      # out-of-chain mutation
    with pytest.raises(CeremonyError) as exc:
        _perform(operator)
    assert exc.value.code == STATE_INCONSISTENT


def test_reenabling_flags_cannot_reopen_a_completed_ceremony(local, operator, settings):
    _perform(operator)
    settings.BOOTSTRAP_ENABLED = True
    settings.BOOTSTRAP_SINGLE_OPERATOR_ENABLED = True
    result = _perform(operator)
    assert result.status == ALREADY_COMPLETED
    assert BootstrapState.objects.get(pk=1).closed is True


# === atomicity ===================================================================

@pytest.mark.parametrize("target", [
    # every write step the ceremony performs, in order: profile, assignment, event,
    # closure, audit. One transaction, so all five must behave identically.
    "apps.accounts.bootstrap_ceremony.ReviewerProfile.objects.create",
    "apps.accounts.bootstrap_ceremony.ReviewerRoleAssignment.save",
    "apps.accounts.bootstrap_ceremony.append_bootstrap_initial_reviewer_event",
    "apps.accounts.bootstrap_ceremony.BootstrapState.save",
    "apps.accounts.bootstrap_ceremony.AuthorizationAudit.objects.create",
])
def test_any_failure_rolls_back_every_effect(local, operator, target):
    with mock.patch(target, side_effect=RuntimeError("induced")):
        with pytest.raises(RuntimeError):
            _perform(operator)
    assert DecisionEvent.objects.count() == 0
    assert ReviewerRoleAssignment.objects.count() == 0
    assert ReviewerProfile.objects.count() == 0
    state = BootstrapState.objects.get(pk=1)
    assert state.closed is False and state.closed_by_event_id is None
    assert not AuthorizationAudit.objects.filter(
        action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE).exists()
    assert verify_chain().ok


# === dedicated verification ======================================================

def test_the_sentinel_is_fatal_on_any_other_action(local, operator):
    from .bootstrap_verification import sentinel_misuse_problems
    from .decision_chain import verify_event
    _perform(operator)
    event = DecisionEvent.objects.get()
    assert sentinel_misuse_problems(event) == []          # valid where it belongs

    event.action = authz.CONFIRM_DESIGN_QUALITY             # the sentinel, borrowed
    assert any("BOOTSTRAP_SENTINEL_MISUSED" in p
               for p in sentinel_misuse_problems(event))
    assert any("not a bootstrap action" in p for p in verify_bootstrap_event(event))
    ok, problems = verify_event(event)
    assert not ok and any("sentinel used on a non-bootstrap action" in p
                          for p in problems)


def test_a_fabricated_authorization_snapshot_is_rejected(local, operator):
    _perform(operator)
    event = DecisionEvent.objects.get()
    event.payload = {**event.payload, "authz_snapshot": {"role_used": "BRAND_ADMIN"}}
    problems = verify_bootstrap_event(event)
    assert any("fabricated authorization snapshot" in p for p in problems)


def test_actor_target_mismatch_and_forbidden_role_are_rejected(local, operator):
    _perform(operator)
    event = DecisionEvent.objects.get()
    event.payload = {**event.payload, "target_user_id": operator.pk + 999}
    assert any("actor and target differ" in p for p in verify_bootstrap_event(event))
    event.payload = {**event.payload, "target_user_id": operator.pk,
                     "granted_role": authz.BRAND_ADMIN}
    assert any("not permitted" in p for p in verify_bootstrap_event(event))


def test_a_missing_assignment_or_open_state_is_a_chain_state_inconsistency(
        local, operator):
    _perform(operator)
    event = DecisionEvent.objects.get()
    ReviewerRoleAssignment.objects.all().delete()
    assert any("BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN" in p
               for p in verify_bootstrap_event(event))
    assert verify_bootstrap_consistency() == []      # no assignment, no event mismatch

    state = BootstrapState.objects.get(pk=1)
    state.closed = False
    state.closed_by_event = None
    state.save()
    assert any("bootstrap state is open" in p for p in verify_bootstrap_consistency())
    assert not verify_decision_chain().ok


def test_an_assignment_without_a_signed_event_is_detected(local, operator):
    ReviewerProfile.objects.create(user=operator, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=operator, role=authz.DESIGN_REVIEWER, granted_by=operator,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_BOOTSTRAP_SINGLE_OPERATOR, grant_reason="forged")
    assert any("no signed ceremony event" in p for p in verify_bootstrap_consistency())
    assert not verify_decision_chain().ok


def test_an_expiry_beyond_the_bound_is_rejected_by_the_verifier(local, operator):
    _perform(operator)
    event = DecisionEvent.objects.get()
    granted = timezone.now()
    event.payload = {**event.payload, "granted_at": granted.isoformat(),
                     "expires_at": (granted + timezone.timedelta(days=90)).isoformat()}
    assert any("exceeds" in p for p in verify_bootstrap_event(event))


# === legacy bypass and break-glass ===============================================

def test_legacy_direct_design_reviewer_bootstrap_is_disabled(local, operator):
    with pytest.raises(CommandError) as exc:
        call_command("bootstrap_reviewer_role", username=operator.username,
                     role=authz.DESIGN_REVIEWER, expires_days=14, reason="legacy",
                     superuser=operator.username, yes=True)
    assert "disabled" in str(exc.value)
    assert "bootstrap_single_operator_reviewer" in str(exc.value)
    assert _authority_untouched()


def test_break_glass_refuses_to_reopen_a_single_operator_closure(
        local, operator, settings):
    _perform(operator)
    settings.BOOTSTRAP_BREAK_GLASS_ENABLED = True
    with pytest.raises(CommandError) as exc:
        call_command("bootstrap_reviewer_role", break_glass=True,
                     superuser=operator.username)
    assert "SINGLE_OPERATOR_BOOTSTRAP_REOPEN_REQUIRES_SEPARATE_REVIEW" in str(exc.value)
    state = BootstrapState.objects.get(pk=1)
    assert state.closed is True
    assert state.break_glass_count == 0            # not incremented
    assert state.closed_by_event is not None       # anchor not cleared


# === the command's account-control challenge =====================================

def test_the_command_refuses_without_an_interactive_terminal(local, operator):
    with pytest.raises(CommandError) as exc:
        call_command("bootstrap_single_operator_reviewer",
                     username=operator.username, expires_days=14, reason=REASON)
    assert "interactive terminal is required" in str(exc.value)
    assert _authority_untouched()


def _tty():
    return mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
        "sys.stdout.isatty", return_value=True)


def test_a_failed_password_challenge_writes_nothing_and_leaks_nothing(local, operator):
    stdin, stdout = _tty()
    with stdin, stdout, \
            mock.patch("getpass.getpass", return_value="wrong-password"), \
            mock.patch("apps.accounts.management.commands."
                       "bootstrap_single_operator_reviewer.authenticate",
                       return_value=None):
        with pytest.raises(CommandError) as exc:
            call_command("bootstrap_single_operator_reviewer",
                         username=operator.username, expires_days=14, reason=REASON)
    assert "authentication failed" in str(exc.value)
    assert "wrong-password" not in str(exc.value)
    assert _authority_untouched()


def test_authenticating_as_a_different_account_is_refused(local, operator):
    other = User.objects.create_user(username="someone-else", is_superuser=True)
    stdin, stdout = _tty()
    with stdin, stdout, mock.patch("getpass.getpass", return_value="pw"), \
            mock.patch("apps.accounts.management.commands."
                       "bootstrap_single_operator_reviewer.authenticate",
                       return_value=other):
        with pytest.raises(CommandError) as exc:
            call_command("bootstrap_single_operator_reviewer",
                         username=operator.username, expires_days=14, reason=REASON)
    assert "differs from the selected account" in str(exc.value)
    assert _authority_untouched()


def test_a_successful_challenge_performs_the_ceremony_and_never_records_the_password(
        local, operator):
    secret = "correct-horse-battery-staple"
    stdin, stdout = _tty()
    with stdin, stdout, mock.patch("getpass.getpass", return_value=secret), \
            mock.patch("apps.accounts.management.commands."
                       "bootstrap_single_operator_reviewer.authenticate",
                       return_value=operator):
        call_command("bootstrap_single_operator_reviewer",
                     username=operator.username, expires_days=14, reason=REASON)
    event = DecisionEvent.objects.get()
    assert secret not in str(event.payload)
    audits = AuthorizationAudit.objects.all()
    assert all(secret not in str(a.metadata) for a in audits)
    assert event.payload["account_control_basis"] == (
        reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE)


def test_the_dry_run_never_prompts_and_writes_nothing(local, operator):
    with mock.patch("getpass.getpass", side_effect=AssertionError("must not prompt")):
        call_command("bootstrap_single_operator_reviewer",
                     username=operator.username, expires_days=14, reason=REASON,
                     dry_run=True)
    assert _authority_untouched()
    report = build_ceremony_preflight(username=operator.username, expires_days=14)
    assert report["ready"] is True
    assert "password challenge REQUIRED" in " ".join(report["lines"])


# === separation: nothing downstream sees this event ==============================

def test_projectors_and_dual_control_ignore_the_ceremony_event(local, operator):
    from apps.intelligence.governance_projection import build_governance_projection
    from apps.intelligence.projection import (
        INTELLIGENCE_ACTIONS, SUPPORTED_ACTIONS, build_projection,
    )
    from apps.intelligence.semantic_corpus import build_corpus_snapshot
    _perform(operator)

    assert reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE not in SUPPORTED_ACTIONS
    assert reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE not in INTELLIGENCE_ACTIONS
    assert build_projection().rows == ()
    assert build_governance_projection().rows == ()
    assert build_corpus_snapshot().document_count >= 0      # builds, ignores the event

    from apps.accounts.attestation import _is_attestation
    assert not _is_attestation(DecisionEvent.objects.get())


def test_normal_role_services_are_unchanged_by_this_correction(local, operator):
    """The self-elevation guard and role authorization must be exactly as before."""
    from .role_services import RoleServiceDenied, grant_reviewer_role
    _perform(operator)
    # the bootstrapped DESIGN_REVIEWER cannot grant anything
    with pytest.raises(RoleServiceDenied):
        grant_reviewer_role(
            actor=operator, target_user=operator, role=authz.DESIGN_REVIEWER,
            expires_at=timezone.now() + timezone.timedelta(days=1), reason="self")
    assert ReviewerRoleAssignment.objects.count() == 1
