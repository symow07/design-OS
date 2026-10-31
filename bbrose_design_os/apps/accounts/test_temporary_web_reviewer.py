"""TEMPORARY WEB-REFERENCE REVIEW AUTHORITY — owner-authorized 14-day grant.

Runs in the honest post-reaffirmation world (legacy epoch lost, ceremony
complete) and proves the grant is bounded: web-source review endpoints only,
no chain action, no role administration, no fork resolution, no artwork
reuse, native expiry, idempotent."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts import bootstrap_registry as reg
from apps.accounts import chain_verification, reaffirmation, web_review_grant
from apps.accounts.authorization import authorize_actor
from apps.accounts.decision_chain import event_integrity_state, verify_event
from apps.accounts.models import (
    GRANT_OWNER_TEMPORARY_WEB_REVIEW,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from apps.accounts.test_reaffirmation_ceremony import (
    _declare_lost,
    _legacy_world,
    _packet_copy,
)
from apps.pipeline.models import DesignProject, DesignTask, WebResearchSession

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture()
def epochs(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"lost-epoch": "c" * 32,
                                         "live-epoch": "d" * 32}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "lost-epoch"
    settings.BOOTSTRAP_ENABLED = True
    settings.BOOTSTRAP_SINGLE_OPERATOR_ENABLED = True
    settings.DEBUG = True
    settings.ENVIRONMENT = "LOCAL_DEVELOPMENT"
    settings.LOCAL_DEVELOPMENT_DATABASES = [
        settings.DATABASES["default"]["NAME"]]
    from apps.accounts.security import signing
    signing.reset_registry()
    yield settings
    signing.reset_registry()


def _post_reaffirmation_world(settings, monkeypatch):
    operator, item, first, second = _legacy_world(settings)
    _declare_lost(monkeypatch)
    import shutil
    tmp, packet_path = _packet_copy()
    try:
        reaffirmation.perform_reaffirmation_ceremony(
            actor=operator, packet_path=packet_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return operator


class TestGrantCeremony:
    def test_grant_is_new_epoch2_authority_independent_of_legacy(
            self, epochs, monkeypatch):
        operator = _post_reaffirmation_world(epochs, monkeypatch)
        result = web_review_grant.grant_temporary_web_reviewer(
            actor=operator)
        assert result.status == "PERFORMED"
        event = DecisionEvent.objects.get(event_id=result.event_id)
        # epoch-2 signed, VERIFIED, references the CLOSURE (not the legacy
        # grant), and its assignment uses the owner-temporary source
        assert event.signing_key_id == "live-epoch"
        assert verify_event(event)[0] is True
        assert event_integrity_state(event) == "VERIFIED"
        closure = DecisionEvent.objects.get(
            action=reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE)
        assert event.payload["reaffirmation_closure_event_id"] == \
            closure.event_id
        legacy_grant = DecisionEvent.objects.get(
            action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE)
        assert legacy_grant.event_id not in str(event.payload)
        assignment = ReviewerRoleAssignment.objects.get(
            pk=result.assignment_id)
        assert assignment.role == authz.WEB_REFERENCE_REVIEWER
        assert assignment.grant_source == GRANT_OWNER_TEMPORARY_WEB_REVIEW
        # 14-day window, to the second
        assert (assignment.expires_at - assignment.granted_at) == \
            timezone.timedelta(days=reg.TEMP_GRANT_MAX_DAYS)
        # statements + capability inventory signed verbatim
        assert tuple(event.payload["statements"]) == \
            reg.TEMP_GRANT_REQUIRED_STATEMENTS
        assert tuple(event.payload["capability_inventory"]) == \
            reg.TEMP_GRANT_CAPABILITIES
        # chain verifies with the grant present
        report = chain_verification.verify_decision_chain()
        assert report.ok is True and report.fatal == ()
        # the revoked legacy reviewer assignment stays revoked
        legacy_assignment = ReviewerRoleAssignment.objects.get(
            grant_source="BOOTSTRAP_SINGLE_OPERATOR")
        assert legacy_assignment.revoked_at is not None

    def test_grant_is_idempotent_and_revocable(self, epochs, monkeypatch):
        operator = _post_reaffirmation_world(epochs, monkeypatch)
        r1 = web_review_grant.grant_temporary_web_reviewer(actor=operator)
        r2 = web_review_grant.grant_temporary_web_reviewer(actor=operator)
        assert r2.status == "ALREADY_GRANTED"
        assert r1.event_id == r2.event_id
        assert DecisionEvent.objects.filter(
            action=reg.TEMPORARY_WEB_REVIEWER_GRANT).count() == 1
        assert web_review_grant.revoke_temporary_web_reviewer(
            actor=operator, reason="review complete") == 1
        assert web_review_grant.active_temporary_web_review_assignment(
            operator) is None
        # superuser/staff untouched throughout
        operator.refresh_from_db()
        assert operator.is_superuser and operator.is_active

    def test_expiry_is_enforced(self, epochs, monkeypatch):
        operator = _post_reaffirmation_world(epochs, monkeypatch)
        web_review_grant.grant_temporary_web_reviewer(actor=operator)
        now = timezone.now()
        assert web_review_grant.active_temporary_web_review_assignment(
            operator, at=now) is not None
        after = now + timezone.timedelta(days=reg.TEMP_GRANT_MAX_DAYS,
                                         seconds=1)
        assert web_review_grant.active_temporary_web_review_assignment(
            operator, at=after) is None

    def test_scope_rejects_chain_actions_roles_and_fork(self, epochs,
                                                        monkeypatch):
        operator = _post_reaffirmation_world(epochs, monkeypatch)
        web_review_grant.grant_temporary_web_reviewer(actor=operator)
        grantee = User.objects.create_user(username="temp-web-reviewer")
        # give the grantee an enabled profile + the temp assignment so the
        # denial is provably the ROLE's doing, not a missing profile
        ReviewerProfile.objects.create(user=grantee, reviewer_enabled=True)
        ReviewerRoleAssignment.objects.create(
            user=grantee, role=authz.WEB_REFERENCE_REVIEWER,
            granted_by=operator, granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=1),
            grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW,
            grant_reason="scope test")
        for action in (authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT,
                       authz.RECORD_HUMAN_SEMANTIC_METADATA,
                       authz.GRANT_REVIEWER_ROLE,
                       authz.REVOKE_REVIEWER_ROLE,
                       authz.CONFIRM_DESIGN_QUALITY):
            assert authorize_actor(grantee, action).allowed is False


class TestEndpointScope:
    @pytest.fixture(autouse=True)
    def _remove_made_folders(self):
        """Each test removes the thumbnail folders its sources were given, when it ends."""
        self._made_folders = []
        yield
        for folder in self._made_folders:
            shutil.rmtree(folder, True)

    def _grantee_client(self, client, operator):
        grantee = User.objects.create_user(username="webrev", password="pw")
        ReviewerRoleAssignment.objects.create(
            user=grantee, role=authz.WEB_REFERENCE_REVIEWER,
            granted_by=operator, granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=14),
            grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW,
            grant_reason="endpoint test")
        client.force_login(grantee)
        return grantee

    def _session_with_sources(self):
        session = WebResearchSession.objects.create(
            product_identity="x", modes=[], status="AWAITING_HUMAN_REVIEW")
        tmp = tempfile.mkdtemp(prefix="thumb_")
        self._made_folders.append(tmp)
        img = Path(tmp) / "img.png"
        from io import BytesIO

        from PIL import Image
        buf = BytesIO()
        Image.new("L", (4, 4), 7).save(buf, "PNG")
        img.write_bytes(buf.getvalue())
        viewable = session.sources.create(
            original_url="https://a.example/i.png", classification="image",
            title="candidate", source_tier=6, mime_type="image/png",
            quarantine_path=str(img))
        weapon = session.sources.create(
            original_url="https://guns.example/rifle.jpg",
            classification="image", title="rifle", source_tier=6,
            mime_type="image/jpeg", quarantine_path=str(img))
        return session, viewable, weapon

    def test_grant_holder_can_review_and_denials_hold(self, epochs,
                                                      monkeypatch, client):
        operator = _post_reaffirmation_world(epochs, monkeypatch)
        self._grantee_client(client, operator)
        session, viewable, weapon = self._session_with_sources()
        base = "/api/web-research"

        assert client.get(f"{base}/sessions/{session.id}/").status_code == 200
        # reference-view only: visible bytes, no classification, no
        # provider input
        r = client.post(f"{base}/sources/{viewable.id}/decision/",
                        {"decision": "approve_reference_view"},
                        content_type="application/json")
        assert r.status_code == 200
        viewable.refresh_from_db()
        assert viewable.reference_view_permission is True
        assert viewable.human_review_state == "UNREVIEWED"
        assert viewable.provider_input_permission is False
        assert client.get(
            f"{base}/sources/{viewable.id}/thumbnail/").status_code == 200
        # rejection with recorded reason → non-viewable
        r = client.post(f"{base}/sources/{weapon.id}/decision/",
                        {"decision": "reject",
                         "reason": "WEB_RESULT_IRRELEVANT_SKU_COLLISION"},
                        content_type="application/json")
        assert r.status_code == 200
        weapon.refresh_from_db()
        assert weapon.human_review_state == "REJECTED"
        assert weapon.reference_view_permission is False
        assert any(w.get("value") == "WEB_RESULT_IRRELEVANT_SKU_COLLISION"
                   for w in weapon.extraction_warnings
                   if isinstance(w, dict))
        assert client.get(
            f"{base}/sources/{weapon.id}/thumbnail/").status_code == 404
        # the classification decisions the scope permits
        for d in ("approve_analog", "approve_inspiration",
                  "approve_fact_source", "needs_verification"):
            assert client.post(f"{base}/sources/{viewable.id}/decision/",
                               {"decision": d},
                               content_type="application/json"
                               ).status_code == 200
        # artwork reuse / design memory decisions DO NOT EXIST
        for d in ("approve_artwork_reuse", "approve_design_memory"):
            assert client.post(f"{base}/sources/{viewable.id}/decision/",
                               {"decision": d},
                               content_type="application/json"
                               ).status_code == 400
        viewable.refresh_from_db()
        assert viewable.artwork_reuse_permission is False
        assert viewable.design_memory_permission is False
        # gate endpoints stay closed to the grant holder
        assert client.post("/api/tasks/51/gate2_approve/",
                           {}, content_type="application/json"
                           ).status_code in (403, 404)
        assert (DesignProject.objects.count(),
                DesignTask.objects.count()) == (0, 0)

    def test_no_grant_no_access_and_expired_grant_denied(self, epochs,
                                                         monkeypatch, client):
        operator = _post_reaffirmation_world(epochs, monkeypatch)
        session, viewable, _ = self._session_with_sources()
        nobody = User.objects.create_user(username="nobody", password="pw")
        client.force_login(nobody)
        assert client.get(
            f"/api/web-research/sessions/{session.id}/").status_code == 403
        ReviewerRoleAssignment.objects.create(
            user=nobody, role=authz.WEB_REFERENCE_REVIEWER,
            granted_by=operator,
            granted_at=timezone.now() - timezone.timedelta(days=20),
            expires_at=timezone.now() - timezone.timedelta(days=6),
            grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW,
            grant_reason="expired")
        assert client.get(
            f"/api/web-research/sessions/{session.id}/").status_code == 403
