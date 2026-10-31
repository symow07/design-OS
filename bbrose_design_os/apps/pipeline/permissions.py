"""Role-based DRF permissions (Milestone 11.1 / audit H2).

Roles are plain ``django.contrib.auth`` Groups, seeded idempotently by
``manage.py seed_roles``:

  Designer — creates and submits tasks
  Reviewer — decides gates (approve/reject), edits prompts, triggers reruns
  Admin    — can do both

Superusers always pass every check (they are the operational escape hatch,
and all pre-Phase-11 accounts/tests use them).
"""
from rest_framework.permissions import BasePermission

ROLE_DESIGNER = "Designer"
ROLE_REVIEWER = "Reviewer"
ROLE_ADMIN = "Admin"

ALL_ROLES = (ROLE_DESIGNER, ROLE_REVIEWER, ROLE_ADMIN)


def user_has_role(user, *roles):
    """True when the user is a superuser or belongs to any of the groups."""
    if not (user and user.is_authenticated):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()


class IsDesigner(BasePermission):
    """Designers (and Admins) create and submit tasks."""

    message = "Only Designers or Admins can create tasks."

    def has_permission(self, request, view):
        return user_has_role(request.user, ROLE_DESIGNER, ROLE_ADMIN)


class IsReviewer(BasePermission):
    """Only Reviewers (and Admins) decide gates."""

    message = "Only Reviewers or Admins can decide gates."

    def has_permission(self, request, view):
        return user_has_role(request.user, ROLE_REVIEWER, ROLE_ADMIN)


class IsWebReferenceReviewer(BasePermission):
    """Web-source review endpoints ONLY (temporary_web_reference_reviewer_grant/1.0).

    Passes for Reviewers/Admins/superusers as before, and additionally for a
    holder of an ACTIVE (unexpired, unrevoked) owner-granted
    WEB_REFERENCE_REVIEWER assignment. That assignment confers exactly this —
    it authorizes no decision-chain action, no gate decision, no role
    administration. Expiry is enforced here on every request.
    """

    message = ("Web-reference review requires Reviewer/Admin standing or an "
               "active temporary web-reference reviewer grant.")

    def has_permission(self, request, view):
        if user_has_role(request.user, ROLE_REVIEWER, ROLE_ADMIN):
            return True
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        from apps.accounts.web_review_grant import (
            active_temporary_web_review_assignment,
        )
        return active_temporary_web_review_assignment(user) is not None


class IsTeamMember(BasePermission):
    """Any role at all (hardening 2026-07-04).

    Read endpoints were previously open to EVERY authenticated account. The
    team-visibility model is deliberate (a small studio sees each other's
    work), but a roleless account — a future client login, a stale invite, a
    service account — must not inherit full visibility by merely existing.
    Membership in any of Designer/Reviewer/Admin is the boundary.
    """

    message = "Your account has no role — ask an admin to add you to a team role."

    def has_permission(self, request, view):
        return user_has_role(request.user, *ALL_ROLES)
