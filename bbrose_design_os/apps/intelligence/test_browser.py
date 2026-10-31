from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    GRANT_TEST_FIXTURE, AuthorizationAudit, DecisionEvent, ReviewerProfile,
    ReviewerRoleAssignment,
)

from .models import (
    CorpusItem, EvidenceReference, OperationalPermissionProjection, SourceArtifact,
)

pytestmark = pytest.mark.django_db
H1 = "1" * 64
H2 = "2" * 64


def _reviewer(*, role=authz.DESIGN_REVIEWER, enabled=True, active=True):
    User = get_user_model()
    granter = User.objects.create_user(username=f"granter-{role}-{enabled}-{active}")
    user = User.objects.create_user(
        username=f"reviewer-{role}-{enabled}-{active}", is_active=active)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="browser fixture")
    return user


def _item():
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key="asset:browser")
    artifact = SourceArtifact.objects.create(
        source_identifier="bounded-source", source_location="/Users/private/secret.ai",
        source_type=SourceArtifact.SourceType.FILE, sha256=H1,
        parser_identifier="test", parser_version="1", source_schema_version="1")
    EvidenceReference.objects.create(
        corpus_item=item, source_artifact=artifact, evidence_kind="SOURCE_FILE",
        locator={"path": "materials/logical.ai"},
        locator_schema_version="source_file/1.0", evidence_hash=H2)
    return item


def test_unauthenticated_inactive_disabled_and_unauthorized_users_are_denied(client):
    item = _item()
    url = reverse("intelligence:corpus-detail", args=[item.pk])
    assert client.get(url).status_code == 403
    for user in (
        _reviewer(active=False),
        _reviewer(enabled=False),
        _reviewer(role=authz.OBSERVER),
    ):
        client.force_login(user)
        assert client.get(url).status_code == 403
        client.logout()


def test_authorized_reviewer_browses_without_retrieval_permission_or_decisions(client):
    item = _item()
    user = _reviewer()
    client.force_login(user)
    before_content = CorpusItem.objects.count()
    response = client.get(reverse("intelligence:corpus-list"))
    assert response.status_code == 200
    assert b"not semantic search or operational retrieval" in response.content
    assert b"Projection status</dt><dd>NOT_BUILT" in response.content
    assert b"Operational permission</dt><dd class=\"denied\">DENIED" in response.content
    detail = client.get(reverse("intelligence:corpus-detail", args=[item.pk]))
    assert detail.status_code == 200
    assert b"PROJECTION STATUS" in detail.content and b"NOT_BUILT" in detail.content
    assert b"OPERATIONAL PERMISSION" in detail.content and b"DENIED" in detail.content
    assert b"LEGACY_SIGNAL_NON_AUTHORITATIVE" in detail.content
    assert b"/Users/private/secret.ai" not in detail.content
    assert b"materials/logical.ai" in detail.content
    assert CorpusItem.objects.count() == before_content
    assert DecisionEvent.objects.count() == 0
    assert OperationalPermissionProjection.objects.count() == 0
    assert AuthorizationAudit.objects.filter(
        user=user, action=authz.REVIEW_EVIDENCE, result="ALLOWED").count() == 2


def test_browser_is_get_only_and_filters_are_bounded(client):
    _item()
    client.force_login(_reviewer())
    url = reverse("intelligence:corpus-list")
    assert client.post(url).status_code == 405
    assert client.get(url, {"q": "x" * 101}).status_code == 400
    assert client.get(url, {"kind": "UNKNOWN_KIND"}).status_code == 400
    assert DecisionEvent.objects.count() == 0


def test_unverified_allowed_projection_is_displayed_as_review_required(client):
    item = _item()
    OperationalPermissionProjection.objects.create(
        corpus_item=item,
        permission_type=OperationalPermissionProjection.Permission.RETRIEVAL,
        effective_state=OperationalPermissionProjection.State.ALLOWED,
        projection_version="operational_permission/1.0",
        reason_code="UNVERIFIED_TEST_ROW",
    )
    client.force_login(_reviewer())

    response = client.get(reverse("intelligence:corpus-detail", args=[item.pk]))

    assert response.status_code == 200
    retrieval = next(
        result for result in response.context["permission_results"]
        if result.permission_type
        == OperationalPermissionProjection.Permission.RETRIEVAL
    )
    assert retrieval.allowed is False
    assert (
        retrieval.effective_state
        == OperationalPermissionProjection.State.REVIEW_REQUIRED
    )
    assert b"REVIEW_REQUIRED" in response.content
    assert DecisionEvent.objects.count() == 0
