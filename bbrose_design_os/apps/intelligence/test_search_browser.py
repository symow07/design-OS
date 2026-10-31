"""Reviewer search browser surface — DIP-1B-6.

Defends: the search page is reachable only by an authorized, enabled, active reviewer;
it reuses the canonical review-access action (no second identity system); operational
modes are not unlocked merely by being able to browse; unknown filters are refused; GET
writes nothing; and the page states plainly that search is not authorization.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    GRANT_TEST_FIXTURE, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
    active_roles,
)

from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection,
)
from .test_review_campaign import asset, brand

pytestmark = pytest.mark.django_db
_seq = 0

# §BH48(b)-0: THE GRANT IS DATED IN THE PAST. `active_at` (apps/accounts/models.py) admits an
# assignment only while `granted_at <= at`, and the view reads `at` from the wall clock when
# the request arrives. A grant dated `timezone.now()` is therefore active only for as long as
# the request's clock reading is not EARLIER than the grant's — a race this fixture lost once,
# at the §BH48(b)(i) gate (.tier2_captures/20260912T055033Z_7bd54e4.txt: 403 NO_ACTIVE_ROLE on a
# role granted milliseconds before), and that the same order did not reproduce. Dating the
# grant GRANT_LEAD in the past keeps the assignment active for any request whose clock is
# within GRANT_LEAD of the grant's. The resolver is not loosened: it stays fail-closed.
GRANT_LEAD = timezone.timedelta(minutes=5)


def _reviewer(*, role=authz.DESIGN_REVIEWER, enabled=True, active=True):
    global _seq
    _seq += 1
    User = get_user_model()
    granter = User.objects.create_user(username=f"s-granter-{_seq}")
    user = User.objects.create_user(username=f"s-reviewer-{_seq}", is_active=active)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    granted_at = timezone.now() - GRANT_LEAD
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=granted_at,
        expires_at=granted_at + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="search browser fixture")
    return user


def _authority_counts():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count())


def test_unauthenticated_inactive_disabled_and_unauthorized_are_denied(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    url = reverse("intelligence:search")
    assert client.get(url).status_code == 403
    for user in (_reviewer(active=False), _reviewer(enabled=False),
                 _reviewer(role=authz.OBSERVER)):
        client.force_login(user)
        assert client.get(url).status_code == 403
        client.logout()


def test_authorized_reviewer_searches_without_retrieval_permission(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    before = _authority_counts()
    response = client.get(reverse("intelligence:search"))
    assert response.status_code == 200
    assert response.context["search"]["total_results"] >= 1
    assert _authority_counts() == before        # GET wrote nothing


def test_page_states_search_is_not_authorization(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    response = client.get(reverse("intelligence:search"))
    body = response.content.decode()
    assert "CANDIDATE SEARCH DOES NOT AUTHORIZE OPERATIONAL USE." in body
    # never mislabelled as semantic: with no published index the page says so in words,
    # and the payload says so in a field a caller can check
    assert "NOT SEMANTIC" in body
    assert response.context["search"]["ranking_is_semantic"] is False


def test_operational_and_automatic_modes_return_empty_fail_closed(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    client.force_login(_reviewer())
    url = reverse("intelligence:search")
    for mode in ("OPERATIONAL_RETRIEVAL", "AUTOMATIC_USE"):
        response = client.get(url, {"mode": mode})
        assert response.status_code == 200
        assert response.context["search"]["total_results"] == 0


@pytest.mark.parametrize("params", [
    {"mode": "SEMANTIC_SEARCH"},
    {"scope": "EVERYTHING"},
    {"item_kind": "NOT_A_KIND"},
    {"wave": "WAVE_9"},
    {"readiness": "APPROVED"},
    {"limit": "500"},
])
def test_unknown_filters_are_refused(client, params):
    client.force_login(_reviewer())
    assert client.get(reverse("intelligence:search"), params).status_code == 400


def test_post_is_rejected_search_is_get_only(client):
    client.force_login(_reviewer())
    assert client.post(reverse("intelligence:search")).status_code == 405


def test_results_never_leak_absolute_paths(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    body = client.get(reverse("intelligence:search")).content.decode()
    assert "/Users/" not in body


def test_the_fixture_dates_its_grant_in_the_past_so_a_request_clock_behind_it_still_finds_the_role():
    """§BH48(b)-0 guard — red on the fixture that granted at `timezone.now()`.

    The request's `at` is a second reading of the wall clock, taken after the grant's; the
    two agree only while the clock never moves backwards between them. This pins that a
    reading up to GRANT_LEAD - 1 s BEHIND the grant's own still resolves the role, and that
    the assignment still expires one day after the instant it was granted.
    """
    user = _reviewer()
    assignment = ReviewerRoleAssignment.objects.get(user=user)
    behind = timezone.now() - GRANT_LEAD + timezone.timedelta(seconds=1)
    assert assignment.granted_at <= behind
    assert authz.DESIGN_REVIEWER in active_roles(user, at=behind)
    assert authz.DESIGN_REVIEWER in active_roles(user)
    assert assignment.expires_at == assignment.granted_at + timezone.timedelta(days=1)
