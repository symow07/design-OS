"""Authorization service, enforcement, audit — DIP-1A-3.

The security-critical behaviours are verified against reality, not just status codes:
CSRF is tested with enforcement actually on; the fail-closed guarantee is tested by
injecting an audit-write failure and asserting the *action rolled back*; unauthenticated
attempts are tested by inspecting the audit row, not the HTTP code alone.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.test import override_settings
from django.urls import path
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from . import authorization as az
from . import authz_policy as authz
from .authorization import (
    ReviewerActionMixin,
    ReviewerActionPermission,
    authorize_actor,
)
from .pipeline_capability import (
    ACTOR_INACTIVE,
    CAPABILITY_GRANTED,
    CAPABILITY_UNKNOWN,
    NO_ACTOR,
    PIPELINE_CAPABILITIES,
    READ_DESIGN_INTELLIGENCE_CONTEXT,
    authorize_pipeline_read,
)
from .models import (
    GRANT_AUTHORIZED_SERVICE,
    AppendOnlyViolation,
    AuthorizationAudit,
    ReviewerProfile,
    ReviewerRoleAssignment,
)

pytestmark = pytest.mark.django_db
User = get_user_model()

DECISION_ACTION = authz.CONFIRM_DESIGN_QUALITY   # DESIGN_REVIEWER or BRAND_ADMIN
MARKER = "marker-user-rollback-probe"


# --- helpers ---------------------------------------------------------------------
_seq = 0


def reviewer(role=authz.DESIGN_REVIEWER, *, enabled=True, is_active=True, username=None):
    global _seq
    _seq += 1
    u = User.objects.create_user(username=username or f"rev{_seq}", password="x",
                                 is_active=is_active)
    ReviewerProfile.objects.create(user=u, reviewer_enabled=enabled)
    if role is not None:
        granter = User.objects.create_user(username=f"granter{_seq}", password="x")
        ReviewerRoleAssignment(
            user=u, role=role, granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=30),
            grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=granter,
            grant_reason="test").save()
    return u


# =================================================================================
# Test-only views + urlconf (never exposed in production)
# =================================================================================
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([])                       # the decorator IS the gate; no global IsAuth
@az.require_reviewer_action(DECISION_ACTION)
def decision_view(request):
    # a real, observable side effect so fail-closed rollback is verifiable
    User.objects.create_user(username=MARKER, password="x")
    return Response({"ok": True})


class MixinDecisionView(ReviewerActionMixin, View):
    required_action = DECISION_ACTION

    def post(self, request, *args, **kwargs):
        User.objects.create_user(username=MARKER, password="x")
        return JsonResponse({"ok": True})


class ReadGateView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReviewerActionPermission]   # overrides global IsAuthenticated
    required_action = DECISION_ACTION

    def get(self, request):
        return Response({"ok": True})


@ensure_csrf_cookie
def csrf_cookie_view(request):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("t/decision/", decision_view),
    path("t/mixin/", MixinDecisionView.as_view()),
    path("t/read/", ReadGateView.as_view()),
    path("t/csrf/", csrf_cookie_view),
]

pytest_urls = override_settings(ROOT_URLCONF=__name__)


# =================================================================================
# authorize_actor — pure service, every reason code
# =================================================================================
def test_unauthenticated_is_denied():
    from django.contrib.auth.models import AnonymousUser
    r = authorize_actor(AnonymousUser(), DECISION_ACTION)
    assert not r.allowed and r.reason_code == az.UNAUTHENTICATED and r.actor_id is None


def test_inactive_user_denied():
    u = reviewer(is_active=False)
    r = authorize_actor(u, DECISION_ACTION)
    assert r.reason_code == az.USER_INACTIVE


def test_missing_profile_denied():
    u = User.objects.create_user(username="noprof", password="x")
    r = authorize_actor(u, DECISION_ACTION)
    assert r.reason_code == az.REVIEWER_PROFILE_MISSING


def test_disabled_profile_denied():
    u = reviewer(enabled=False)
    r = authorize_actor(u, DECISION_ACTION)
    assert r.reason_code == az.REVIEWER_DISABLED


def test_unknown_action_denied():
    u = reviewer()
    r = authorize_actor(u, "not_a_real_action")
    assert r.reason_code == az.ACTION_UNKNOWN


def test_no_active_role_denied():
    u = reviewer(role=None)
    r = authorize_actor(u, DECISION_ACTION)
    assert r.reason_code == az.NO_ACTIVE_ROLE


def test_role_not_authorized_denied():
    u = reviewer(role=authz.OBSERVER)
    r = authorize_actor(u, DECISION_ACTION)
    assert r.reason_code == az.ROLE_NOT_AUTHORIZED and r.active_roles == (authz.OBSERVER,)


def test_system_admin_forbidden_is_labelled_distinctly():
    u = reviewer(role=authz.SYSTEM_ADMIN)
    r = authorize_actor(u, authz.APPROVE_LICENSE)
    assert r.reason_code == az.SYSTEM_ADMIN_FORBIDDEN


def test_system_admin_forbidden_even_with_a_second_unauthorized_role():
    # holds SYSTEM_ADMIN + DESIGN_REVIEWER; neither may APPROVE_LICENSE -> the forbidden
    # label wins (admin power is not authority), not the generic one.
    u = reviewer(role=authz.SYSTEM_ADMIN)
    granter = User.objects.create_user(username="g-extra", password="x")
    ReviewerRoleAssignment(
        user=u, role=authz.DESIGN_REVIEWER, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
        grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=granter,
        grant_reason="second role").save()
    r = authorize_actor(u, authz.APPROVE_LICENSE)
    assert r.reason_code == az.SYSTEM_ADMIN_FORBIDDEN


def test_expired_role_denied_at_service_level():
    u = reviewer(role=None)
    granter = User.objects.create_user(username="g-exp", password="x")
    ReviewerRoleAssignment(
        user=u, role=authz.DESIGN_REVIEWER,
        granted_at=timezone.now() - timezone.timedelta(days=10),
        expires_at=timezone.now() - timezone.timedelta(days=1),
        grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=granter,
        grant_reason="expired").save()
    assert authorize_actor(u, DECISION_ACTION).reason_code == az.NO_ACTIVE_ROLE


def test_revoked_role_denied_at_service_level():
    u = reviewer(role=None)
    granter = User.objects.create_user(username="g-rev", password="x")
    ReviewerRoleAssignment(
        user=u, role=authz.DESIGN_REVIEWER,
        granted_at=timezone.now() - timezone.timedelta(days=10),
        expires_at=timezone.now() + timezone.timedelta(days=30),
        revoked_at=timezone.now() - timezone.timedelta(days=1), revoked_by=granter,
        revocation_reason="left", grant_source=GRANT_AUTHORIZED_SERVICE,
        granted_by=granter, grant_reason="then revoked").save()
    assert authorize_actor(u, DECISION_ACTION).reason_code == az.NO_ACTIVE_ROLE


def test_authorized_selects_deterministic_role_used():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    r = authorize_actor(u, DECISION_ACTION)
    assert r.allowed and r.reason_code == az.AUTHORIZED
    assert r.role_used == authz.DESIGN_REVIEWER
    assert r.selection_rule == authz.ROLE_SELECTION_RULE


def test_subject_is_recorded_but_never_loosens_the_decision():
    u = reviewer()
    r = authorize_actor(u, DECISION_ACTION, subject=("FontFace", "face-1"))
    assert r.subject_type == "FontFace" and r.subject_id == "face-1"


# =================================================================================
# AuthorizationAudit — append-only, constraint, caps
# =================================================================================
def _allow_result(u):
    return authorize_actor(u, DECISION_ACTION)


def test_audit_row_is_append_only_update_and_delete_refused():
    u = reviewer()
    az.record_authorization(_allow_result(u), endpoint="t")
    row = AuthorizationAudit.objects.get()
    with pytest.raises(AppendOnlyViolation):
        AuthorizationAudit.objects.filter(pk=row.pk).update(reason_code="TAMPERED")
    with pytest.raises(AppendOnlyViolation):
        AuthorizationAudit.objects.filter(pk=row.pk).delete()


def test_audit_row_refuses_resave_of_a_loaded_row():
    u = reviewer()
    az.record_authorization(_allow_result(u), endpoint="t")
    row = AuthorizationAudit.objects.get()
    row.reason_code = "TAMPERED"
    with pytest.raises(AppendOnlyViolation):
        row.save()


def test_audit_db_constraint_allow_requires_role_used():
    from django.db import IntegrityError, transaction
    u = reviewer()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AuthorizationAudit.objects.create(
                user=u, action=DECISION_ACTION, result="ALLOWED",
                reason_code="AUTHORIZED", role_used="", endpoint="t")


def test_correlation_id_rejects_oversized_untrusted_value():
    u = reviewer()

    class FakeReq:
        request_id = "x" * 5000            # an unbounded inbound X-Request-ID
        META = {}
        method = "POST"
    row = az.record_authorization(_allow_result(u), request=FakeReq(), endpoint="t")
    # the junk is discarded and a fresh uuid stored, never truncated-and-kept
    assert row.correlation_id != "x" * 5000
    assert 0 < len(row.correlation_id) <= 64


def test_source_ip_off_by_default():
    u = reviewer()

    class FakeReq:
        META = {"REMOTE_ADDR": "203.0.113.9"}
        method = "POST"
        request_id = "abc"
    row = az.record_authorization(_allow_result(u), request=FakeReq(), endpoint="t")
    assert row.source_ip is None


@override_settings(AUTHORIZATION_AUDIT_RECORD_IP=True,
                   AUTHORIZATION_TRUSTED_PROXIES=["10.0.0.1"])
def test_forwarded_ip_trusted_only_from_configured_proxy():
    u = reviewer()

    class ViaProxy:
        META = {"REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "198.51.100.7, 10.0.0.1"}
        method = "POST"
        request_id = "abc"

    class ViaStranger:
        META = {"REMOTE_ADDR": "192.0.2.50",
                "HTTP_X_FORWARDED_FOR": "198.51.100.7"}
        method = "POST"
        request_id = "abc"
    assert az.record_authorization(_allow_result(u), request=ViaProxy(),
                                   endpoint="t").source_ip == "198.51.100.7"
    # a forged XFF from a non-trusted peer is ignored; the direct address wins
    assert az.record_authorization(_allow_result(u), request=ViaStranger(),
                                   endpoint="t").source_ip == "192.0.2.50"


# =================================================================================
# HTTP enforcement
# =================================================================================
@pytest_urls
def test_allowed_request_writes_audit_and_runs_action():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient()
    c.force_login(u)
    resp = c.post("/t/decision/", {}, format="json")
    assert resp.status_code == 200
    assert User.objects.filter(username=MARKER).exists()
    row = AuthorizationAudit.objects.get(action=DECISION_ACTION, result="ALLOWED")
    assert row.user_id == u.pk and row.role_used == authz.DESIGN_REVIEWER


@pytest_urls
def test_request_body_actor_id_and_role_are_ignored():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient()
    c.force_login(u)
    resp = c.post("/t/decision/",
                  {"actor_id": 999999, "role": authz.BRAND_ADMIN}, format="json")
    assert resp.status_code == 200
    row = AuthorizationAudit.objects.get(result="ALLOWED")
    assert row.user_id == u.pk                       # not 999999
    assert row.role_used == authz.DESIGN_REVIEWER    # not BRAND_ADMIN from the body


@pytest_urls
def test_denied_request_is_audited_and_refused():
    u = reviewer(role=authz.OBSERVER)
    c = APIClient()
    c.force_login(u)
    resp = c.post("/t/decision/", {}, format="json")
    assert resp.status_code == 403
    assert not User.objects.filter(username=MARKER).exists()
    row = AuthorizationAudit.objects.get(result="DENIED")
    assert row.reason_code == az.ROLE_NOT_AUTHORIZED and row.user_id == u.pk


@pytest_urls
def test_fail_closed_audit_write_failure_rolls_back_the_action(monkeypatch):
    """The security core: if the allowed action's audit cannot be written, the action must
    not commit. Inject an audit-write failure and assert the marker row is ABSENT."""
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient()
    c.force_login(u)

    def boom(*a, **k):
        raise RuntimeError("audit backend down")
    monkeypatch.setattr(az, "record_authorization", boom)

    with pytest.raises(RuntimeError):
        c.post("/t/decision/", {}, format="json")
    # the action rolled back with the failed audit — fail closed, not fail open
    assert not User.objects.filter(username=MARKER).exists()


@pytest_urls
def test_denial_audit_failure_still_denies(monkeypatch):
    u = reviewer(role=authz.OBSERVER)
    c = APIClient()
    c.force_login(u)
    monkeypatch.setattr(az, "record_authorization",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    resp = c.post("/t/decision/", {}, format="json")
    assert resp.status_code == 403                    # denial stands despite audit failure
    assert not User.objects.filter(username=MARKER).exists()


@pytest_urls
def test_mixin_enforces_and_audits():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(u)
    resp = c.post("/t/mixin/", {}, format="json")
    assert resp.status_code == 200
    assert AuthorizationAudit.objects.filter(result="ALLOWED").exists()


@pytest_urls
def test_no_sensitive_headers_or_body_are_stored_in_the_audit():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient()
    c.force_login(u)
    # NB: no manual Cookie header — that would clobber force_login's session. The point
    # is that a secret in the body or the Authorization header never reaches the audit row.
    resp = c.post("/t/decision/", {"password": "hunter2", "secret": "s3cr3t"},
                  format="json", HTTP_AUTHORIZATION="Bearer super-secret-token")
    assert resp.status_code == 200
    row = AuthorizationAudit.objects.get(result="ALLOWED")
    blob = repr([row.metadata, row.user_agent, row.correlation_id, row.subject_id,
                 row.subject_type, row.reason_code])
    for secret in ("hunter2", "s3cr3t", "super-secret-token", "sessionid", "csrftoken"):
        assert secret not in blob, f"audit row leaked {secret!r}"


@pytest_urls
def test_get_cannot_perform_a_protected_unsafe_action():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient()
    c.force_login(u)
    resp = c.get("/t/decision/")                       # POST-only decision endpoint
    assert resp.status_code == 405                     # method not allowed
    assert not User.objects.filter(username=MARKER).exists()


@pytest_urls
def test_read_gate_unauthenticated_is_audited_with_null_user():
    c = APIClient()
    resp = c.get("/t/read/")
    assert resp.status_code in (401, 403)
    row = AuthorizationAudit.objects.get()
    assert row.user_id is None and row.reason_code == az.UNAUTHENTICATED


# =================================================================================
# CSRF — enforcement actually ON
# =================================================================================
@pytest_urls
def test_csrf_enforced_missing_token_is_refused_and_not_audited():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient(enforce_csrf_checks=True)
    c.force_login(u)
    resp = c.post("/t/decision/", {}, format="json")     # no CSRF token
    assert resp.status_code == 403
    # CSRF fails at authentication, BEFORE authorization — so nothing was audited
    assert AuthorizationAudit.objects.count() == 0


@pytest_urls
def test_csrf_valid_token_but_unauthorized_role_is_denied_and_audited():
    u = reviewer(role=authz.OBSERVER)
    c = APIClient(enforce_csrf_checks=True)
    c.force_login(u)
    c.get("/t/csrf/")                                    # sets the csrftoken cookie
    token = c.cookies["csrftoken"].value
    resp = c.post("/t/decision/", {}, format="json", HTTP_X_CSRFTOKEN=token)
    assert resp.status_code == 403
    # this time CSRF PASSED and authorization denied -> a DENIED row exists
    assert AuthorizationAudit.objects.filter(reason_code=az.ROLE_NOT_AUTHORIZED).exists()


@pytest_urls
def test_csrf_valid_token_and_authorized_role_succeeds():
    u = reviewer(role=authz.DESIGN_REVIEWER)
    c = APIClient(enforce_csrf_checks=True)
    c.force_login(u)
    c.get("/t/csrf/")
    token = c.cookies["csrftoken"].value
    resp = c.post("/t/decision/", {}, format="json", HTTP_X_CSRFTOKEN=token)
    assert resp.status_code == 200
    assert AuthorizationAudit.objects.filter(result="ALLOWED").exists()


# =================================================================================
# Policy-drift check
# =================================================================================
def test_drift_check_passes_for_known_registered_action():
    from .authorization import PROTECTED_ACTIONS
    from .checks import check_protected_actions_are_known
    az.register_protected_action(DECISION_ACTION)
    assert DECISION_ACTION in PROTECTED_ACTIONS
    assert check_protected_actions_are_known(None) == []


def test_drift_check_flags_an_unknown_registered_action():
    from .authorization import PROTECTED_ACTIONS
    from .checks import check_protected_actions_are_known
    PROTECTED_ACTIONS.add("totally_made_up_action")
    try:
        errors = check_protected_actions_are_known(None)
        assert errors and errors[0].id == "accounts.policy.E003"
    finally:
        PROTECTED_ACTIONS.discard("totally_made_up_action")


# =================================================================================
# "still absent" gates — 1A-4 surface must not exist yet
# =================================================================================
def test_decision_chain_models_exist_as_of_1a4():
    # 1A-3 asserted these did NOT exist; 1A-4 intentionally introduced the signed chain.
    # The assertion is inverted on purpose (not deleted-to-green).
    from django.apps import apps as django_apps
    names = {m.__name__ for m in django_apps.get_app_config("accounts").get_models()}
    assert "DecisionEvent" in names and "DecisionChainHead" in names


def test_accounts_migrations_through_1a5a():
    from pathlib import Path

    from django.conf import settings
    mig = Path(settings.BASE_DIR) / "apps" / "accounts" / "migrations"
    files = sorted(p.name for p in mig.glob("0*.py"))
    # 0004: v2-schema default (state-only). 0005: bootstrap-state singleton (1A-5A).
    # 0006: BOOTSTRAP_SINGLE_OPERATOR grant source (BOOTSTRAP-CORR-2) — choices only, so
    # its sqlmigrate is a no-op and no existing row or column is altered.
    # 0007: OWNER_TEMPORARY_WEB_REVIEW grant source (temporary web-reference
    # reviewer grant, 2026-07-25) — choices only, exactly like 0006.
    assert files == ["0001_initial.py", "0002_authorizationaudit.py",
                     "0003_decisionevent_decisionchainhead.py",
                     "0004_alter_decisionevent_schema_version.py",
                     "0005_bootstrapstate.py",
                     "0006_single_operator_bootstrap_source.py",
                     "0007_alter_reviewerroleassignment_grant_source.py"]


def test_authorization_introduces_no_permission_or_retrieval_flags():
    # 1A-3 decides and audits; it grants no operational permission, retrieval or auto-use.
    import apps.accounts.authorization as mod
    src = mod.__file__
    text = open(src).read()
    for forbidden in ("retrieval", "automatic_use", "auto_use", "production_use",
                      "grant_permission("):
        assert forbidden not in text, f"1A-3 must not introduce {forbidden!r}"


# =================================================================================
# §BH58(d) — THE CAPABILITY SPLIT. Reading the house library is not reviewing.
#
# `authorize_actor` checks reviewer standing at step 2, BEFORE it looks the action
# up, so all 45 policy actions — including a read that supplies no asset and grants
# no permission — sat behind "are you an enabled reviewer". Measured on the owner's
# account: authenticated, active, reviewer profile DISABLED, zero active roles. Every
# run of his brief logged DENIED:REVIEWER_DISABLED and the design saw nothing.
#
# Owner ruling §BH58(d): "Reading the house library to inform a design is not
# reviewing evidence, and a background job is not a person. Split the capability …
# and reviewing stays what it was. Do not grant my account a reviewer role to make a
# machine able to read my own library."
# =================================================================================


@pytest.mark.django_db
def test_every_reviewer_action_still_requires_reviewer_standing():
    """THE TEST THAT CARRIES THE SPLIT. Not a sentence in a commit message — all 45.

    If a later change routes any review action through the pipeline door, or carves a
    conditional into the reviewer gate, this fails.
    """
    disabled = reviewer(role=authz.DESIGN_REVIEWER, enabled=False)
    assert len(authz.ACTIONS) >= 45
    for action in authz.ACTIONS:
        decision = authorize_actor(disabled, action)
        assert not decision.allowed, action
        assert decision.reason_code == az.REVIEWER_DISABLED, (action, decision.reason_code)


@pytest.mark.django_db
def test_the_pipeline_capability_is_not_a_reviewer_action_and_cannot_become_one():
    """The two sets are disjoint, so the new door cannot open a review action even if a
    caller passes one to it."""
    for capability in PIPELINE_CAPABILITIES:
        assert capability not in authz.ACTIONS
    assert PIPELINE_CAPABILITIES == (READ_DESIGN_INTELLIGENCE_CONTEXT,)
    # and handing it a genuine review action is refused by name
    user = reviewer(role=None, enabled=False)
    assert authorize_pipeline_read(user, authz.GRANT_PERMISSION).reason_code \
        == CAPABILITY_UNKNOWN


@pytest.mark.django_db
def test_a_disabled_reviewer_with_no_roles_may_read_design_intelligence_context():
    """The owner's own account, exactly as measured: authenticated, active, reviewer
    profile disabled, zero active roles. This is the state his ruling addresses."""
    user = reviewer(role=None, enabled=False)
    assert not authorize_actor(user, authz.VIEW_INTELLIGENCE_REVIEW_QUEUE).allowed
    decision = authorize_pipeline_read(user, READ_DESIGN_INTELLIGENCE_CONTEXT)
    assert decision.allowed
    assert decision.reason_code == CAPABILITY_GRANTED
    assert decision.actor_id == user.pk


@pytest.mark.django_db
def test_a_user_with_no_reviewer_profile_at_all_may_still_read():
    """"A background job is not a person" — the capability asks nothing about review
    standing, so an account that has never been a reviewer is not refused for it."""
    user = User.objects.create_user(username="plain-actor", password="x")
    assert authorize_actor(user, authz.VIEW_INTELLIGENCE_REVIEW_QUEUE).reason_code \
        == az.REVIEWER_PROFILE_MISSING
    assert authorize_pipeline_read(user, READ_DESIGN_INTELLIGENCE_CONTEXT).allowed


@pytest.mark.django_db
def test_identity_is_still_required_and_the_refusal_names_what_it_measured():
    """§BH58(e): "an exception handler may not assert a cause it did not measure" — the
    same standard for a refusal. None of these reasons is a reviewer reason code, because
    no reviewer check runs here."""
    assert authorize_pipeline_read(None, READ_DESIGN_INTELLIGENCE_CONTEXT).reason_code \
        == NO_ACTOR
    inactive = User.objects.create_user(username="gone", password="x", is_active=False)
    assert authorize_pipeline_read(inactive, READ_DESIGN_INTELLIGENCE_CONTEXT).reason_code \
        == ACTOR_INACTIVE
    for reason in (NO_ACTOR, ACTOR_INACTIVE, CAPABILITY_UNKNOWN):
        assert "REVIEWER" not in reason


@pytest.mark.django_db
def test_the_design_context_reads_through_the_capability_and_not_the_reviewer_gate():
    """End to end at the seam the owner's runs actually take: a disabled reviewer with no
    roles gets AUTHORIZED context metadata instead of DENIED:REVIEWER_DISABLED."""
    from apps.pipeline.design_context import build_design_context
    user = reviewer(role=None, enabled=False)
    brief = {"brand": "BBROSE", "product_name": "Rose Glow Palette",
             "product_category": "CO", "design_target": "product_container",
             "dimensions": "", "preferred_colors": [], "prohibited_colors": [],
             "prohibited_motifs": [], "production_constraints": [],
             "required_copy": [], "references": []}
    context = build_design_context(user, brief)
    assert context["metadata"]["authorization"] == "AUTHORIZED"
    # the read stays a read: no locator, no asset, no permission (design_context contract)
    assert context["references"] == [] or all(
        "path" not in str(key).lower() for reference in context["references"]
        for key in reference)
