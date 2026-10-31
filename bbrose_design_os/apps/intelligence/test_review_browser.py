"""Campaign/readiness browser surface — DIP-1B-5B.

What these tests defend: the queue and packet are reachable only by an authorized,
enabled, active reviewer; every filter is bounded and refuses an unknown value rather
than silently widening the result set; the page states plainly that readiness is not
approval; GET writes nothing and grants nothing; and no governance or permission control
is offered by this surface.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    GRANT_TEST_FIXTURE, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
)

from . import review_campaign as RC
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    DesignAssetProfile, EvidenceReference, GovernanceDecisionProjection,
    HumanAssertionProjection, OperationalPermissionProjection,
    SourceLocationObservation,
)
from .test_review_campaign import asset, brand

pytestmark = pytest.mark.django_db
_seq = 0


def _reviewer(*, role=authz.DESIGN_REVIEWER, enabled=True, active=True):
    global _seq
    _seq += 1
    User = get_user_model()
    granter = User.objects.create_user(username=f"granter-{_seq}")
    user = User.objects.create_user(username=f"reviewer-{_seq}", is_active=active)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="campaign browser fixture")
    return user


def _authority_counts():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count())


# === authorization ==============================================================
def test_unauthenticated_inactive_disabled_and_unauthorized_are_denied(client):
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    for url in (reverse("intelligence:review-queue"),
                reverse("intelligence:review-detail", args=[rc.pk])):
        assert client.get(url).status_code == 403
        for user in (_reviewer(active=False), _reviewer(enabled=False),
                     _reviewer(role=authz.OBSERVER)):
            client.force_login(user)
            assert client.get(url).status_code == 403
            client.logout()


def test_authorized_reviewer_browses_without_any_retrieval_permission(client):
    """Browsing the campaign requires no RETRIEVAL/AUTOMATIC_USE permission, and being
    able to browse must not create one."""
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    before = _authority_counts()
    assert client.get(reverse("intelligence:review-queue")).status_code == 200
    assert client.get(
        reverse("intelligence:review-detail", args=[rc.pk])).status_code == 200
    assert _authority_counts() == before
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()


# === GET is read-only ===========================================================
def test_get_writes_nothing_and_post_to_queue_is_rejected(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    client.force_login(_reviewer())
    url = reverse("intelligence:review-queue")
    before = _authority_counts()
    for params in ({}, {"wave": RC.WAVE_4}, {"readiness": "READY_FOR_CLASSIFICATION"},
                   {"blocker": "RIGHTS_UNREVIEWED"}):
        assert client.get(url, params).status_code == 200
    assert _authority_counts() == before
    assert client.post(url).status_code == 405        # queue is GET-only


# === bounded filters ============================================================
@pytest.mark.parametrize("params", [
    {"wave": "WAVE_9_NOT_A_WAVE"},
    {"readiness": "APPROVED"},               # not in the readiness vocabulary — refused
    {"blocker": "NOT_A_BLOCKER"},
    {"status": "UNKNOWN_STATUS"},
    {"review_type": "UNKNOWN_TYPE"},
    {"assignment": "everyone"},
    {"reviewer": "x" * 151},
])
def test_unknown_filter_values_are_refused_not_silently_ignored(client, params):
    """A silently-dropped filter would show a reviewer a wider set than they believe
    they are looking at."""
    client.force_login(_reviewer())
    assert client.get(
        reverse("intelligence:review-queue"), params).status_code == 400


def test_wave_filter_returns_only_that_wave(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    rc_brand = brand()
    client.force_login(_reviewer())
    response = client.get(reverse("intelligence:review-queue"), {"wave": RC.WAVE_4})
    assert response.status_code == 200
    ids = [c.pk for c in response.context["page"].object_list]
    assert ids == [rc_brand.pk]


def test_blocker_filter_selects_only_blocked_candidates(client):
    brand()                                   # rights + identity blocked
    client.force_login(_reviewer())
    response = client.get(
        reverse("intelligence:review-queue"), {"blocker": "IDENTITY_UNCONFIRMED"})
    assert response.status_code == 200
    assert all("IDENTITY_UNCONFIRMED" in c.readiness.blocker_codes
               for c in response.context["page"].object_list)


def test_queue_ordering_is_deterministic(client):
    for _ in range(3):
        asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        brand()
    client.force_login(_reviewer())
    url = reverse("intelligence:review-queue")
    first = [c.pk for c in client.get(url).context["page"].object_list]
    second = [c.pk for c in client.get(url).context["page"].object_list]
    assert first == second


# === the surface never implies authority ========================================
def test_queue_states_readiness_is_not_approval_and_shows_progress(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    response = client.get(reverse("intelligence:review-queue"))
    body = response.content.decode()
    assert "REVIEW READINESS IS NOT APPROVAL OR OPERATIONAL PERMISSION." in body
    assert response.context["review_tasks_completed"] == 0
    assert response.context["review_tasks_remaining"] == 1


def test_detail_shows_packet_sections_and_offers_no_permission_control(client):
    rc = brand()
    client.force_login(_reviewer())
    body = client.get(
        reverse("intelligence:review-detail", args=[rc.pk])).content.decode()
    for section in ("TECHNICAL EVIDENCE", "PROVENANCE", "MACHINE OUTPUT",
                    "HUMAN ASSERTIONS", "REVIEW READINESS", "GOVERNANCE STATUS",
                    "OPERATIONAL PERMISSION"):
        assert section in body, section
    assert "REVIEW READINESS IS NOT APPROVAL OR OPERATIONAL PERMISSION." in body
    # this surface grants nothing: no permission-granting control exists
    for control in ("grant-permission", "review-grant", "permission-allow"):
        assert control not in body


def test_detail_never_leaks_an_unrestricted_absolute_source_path(client):
    """Seeds an absolute path so the assertion can actually fail: without a
    SourceLocationObservation carrying one, '/Users/' could not appear regardless of
    whether redaction works, and the test would pass for the wrong reason."""
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    profile = DesignAssetProfile.objects.get(corpus_item=rc.corpus_item)
    EvidenceReference.objects.create(
        corpus_item=rc.corpus_item, source_artifact=profile.primary_source_artifact,
        evidence_kind="SOURCE_FILE", locator={"path": "a/b/c.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="d" * 64)
    SourceLocationObservation.objects.create(
        source_artifact=profile.primary_source_artifact,
        observed_location="/Users/secret/materials/private.ai",
        location_kind="REPOSITORY_RELATIVE", availability_state="AVAILABLE")
    client.force_login(_reviewer())
    body = client.get(
        reverse("intelligence:review-detail", args=[rc.pk])).content.decode()
    assert "REDACTED_UNRESTRICTED_PATH" in body      # the guard actually ran
    assert "/Users/secret" not in body


# === machine candidate kind is a display label, never lineage ===================
def test_candidate_kind_filter_selects_by_machine_label_only(client):
    rc_asset = asset(DIP0C2_ASSET_CANDIDATE_DATASET)      # candidate_asset_kind=MOTIF
    brand(kind="LOGO")
    client.force_login(_reviewer())
    response = client.get(
        reverse("intelligence:review-queue"), {"candidate_kind": "MOTIF"})
    assert response.status_code == 200
    assert [c.pk for c in response.context["page"].object_list] == [rc_asset.pk]


def test_candidate_kind_never_moves_a_candidate_between_waves(client):
    """A brand-lineage candidate machine-labelled PALETTE stays WAVE_4 BRAND_IDENTITY.
    The filter may hide it; it may never reclassify it."""
    rc = brand(kind="PALETTE", key="brand:dip0c3-brand:91")
    client.force_login(_reviewer())
    response = client.get(
        reverse("intelligence:review-queue"), {"candidate_kind": "PALETTE"})
    row = next(c for c in response.context["page"].object_list if c.pk == rc.pk)
    assert row.campaign_entry["wave"] == RC.WAVE_4
    assert row.review_type == "BRAND_IDENTITY"


def test_unknown_candidate_kind_is_refused(client):
    client.force_login(_reviewer())
    assert client.get(reverse("intelligence:review-queue"),
                      {"candidate_kind": "NOT_A_KIND"}).status_code == 400


# === fail-closed + stable denominator ===========================================
def test_a_candidate_with_no_lineage_is_withheld_not_guessed(client):
    """An orphan must not 500 the queue, and must not be given an invented wave."""
    from .models import CorpusItem, ReviewCandidate
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key="asset:orphan:browser")
    ReviewCandidate.objects.create(
        corpus_item=item, review_type=ReviewCandidate.ReviewType.DESIGN_ASSET,
        priority=1, review_manifest_id="dip1b_review_manifest/1.0")
    client.force_login(_reviewer())
    response = client.get(reverse("intelligence:review-queue"))
    assert response.status_code == 200
    assert response.context["unreadable_candidates"] == 1
    assert response.context["readiness_counts"] == {}


def test_progress_totals_do_not_move_when_filters_narrow_the_view(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    client.force_login(_reviewer())
    url = reverse("intelligence:review-queue")
    unfiltered = client.get(url).context
    filtered = client.get(url, {"wave": RC.WAVE_4}).context
    # the filter narrows the cards ...
    assert len(filtered["page"].object_list) < len(unfiltered["page"].object_list)
    # ... but how much work exists is not a function of what you are looking at
    assert filtered["review_tasks_total"] == unfiltered["review_tasks_total"] == 2
    assert filtered["readiness_counts"] == unfiltered["readiness_counts"]
