"""Controlled, self-closing bootstrap of the FIRST reviewer authority (DIP-1A-2 / 1A-5A).

The grant/revoke chain has a chicken-and-egg problem: every production grant must name an
authenticated granter, but the very first grant has no prior reviewer. This command breaks
that cycle by writing a `grant_source=BOOTSTRAP` / `granted_by=NULL` assignment — the one
combination the database permits without a granter.

Because that is a standing elevation bypass, 1A-5A **closes it**. Bootstrap is permitted
ONLY when every one of these holds (checked under a row lock on the singleton state):

* the deployment sets `BOOTSTRAP_ENABLED = True`;
* a named, **active Django superuser** operator is supplied (`--superuser`);
* the bootstrap state is not already permanently closed;
* no protected role-management DecisionEvent has ever been recorded;
* no active NON-bootstrap reviewer authority already exists;
* target, role, expiry and reason are explicit.

The state does **not** auto-close here (this command records no DecisionEvent) — it closes
the first time the protected `role_services` append a role-management event. Re-opening a
closed environment is a deliberate `--break-glass` act, itself gated by
`BOOTSTRAP_BREAK_GLASS_ENABLED`, which writes a CRITICAL audit record and grants nothing.

This command is never exposed through the web.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ... import authz_policy as authz
from ... import bootstrap_registry
from ...models import (
    GRANT_BOOTSTRAP,
    RESULT_DENIED,
    AuthorizationAudit,
    BootstrapState,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from ...role_services import ROLE_MGMT_ACTIONS

BREAK_GLASS_REASON = "BOOTSTRAP_BREAK_GLASS_REOPEN"


class Command(BaseCommand):
    help = ("Seed the first reviewer role (grant_source=BOOTSTRAP). Deployment-gated and "
            "self-closing; use rarely.")

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Existing auth.User to make a reviewer.")
        parser.add_argument("--role", help=f"One of {list(authz.ROLES)}.")
        parser.add_argument("--expires-days", type=int,
                            help="Days until the grant expires (required, time-bounded).")
        parser.add_argument("--reason", help="Why this person holds this role (recorded).")
        parser.add_argument("--superuser",
                            help="Username of the active superuser running this ceremony.")
        parser.add_argument("--display-name", default="")
        parser.add_argument("--yes", action="store_true",
                            help="Skip the interactive confirmation.")
        parser.add_argument("--break-glass", action="store_true",
                            help="Re-open a permanently-closed bootstrap (audited CRITICAL; "
                                 "grants nothing). Requires BOOTSTRAP_BREAK_GLASS_ENABLED.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["break_glass"]:
            return self._break_glass(opts)
        return self._bootstrap(opts)

    # --- helpers ------------------------------------------------------------------
    def _active_superuser(self, username):
        User = get_user_model()
        if not username:
            raise CommandError("--superuser (an active superuser operator) is required.")
        try:
            op = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"no user {username!r} to act as the bootstrap operator.")
        if not (op.is_active and op.is_superuser):
            raise CommandError(f"operator {username!r} is not an ACTIVE superuser.")
        return op

    # --- normal bootstrap ---------------------------------------------------------
    def _bootstrap(self, opts):
        if not getattr(settings, "BOOTSTRAP_ENABLED", False):
            raise CommandError(
                "bootstrap is disabled. Set BOOTSTRAP_ENABLED for the seeding ceremony.")
        for req in ("username", "role", "expires_days", "reason"):
            if opts.get(req) in (None, ""):
                raise CommandError(f"--{req.replace('_', '-')} is required.")
        if opts["role"] not in authz.ROLES:
            raise CommandError(f"{opts['role']!r} is not a valid role.")
        if opts["expires_days"] <= 0:
            raise CommandError("--expires-days must be positive.")
        if not opts["reason"].strip():
            raise CommandError("--reason may not be blank.")

        # DIP-1A-BOOTSTRAP-CORR-2: the direct DESIGN_REVIEWER path is CLOSED. It seeded a
        # reviewer without ever recording a protected role-management event, so
        # BootstrapState stayed open forever and only an environment flag stood between the
        # deployment and a repeat. A disabled flag is not permanent structural closure.
        # Reviewer seeding now goes through the single-operator ceremony, which closes
        # bootstrap in the same transaction as the grant.
        if opts["role"] == authz.DESIGN_REVIEWER:
            raise CommandError(
                "direct DESIGN_REVIEWER bootstrap is disabled (DIP-1A-BOOTSTRAP-CORR-2): "
                "it leaves BootstrapState open. Use the single-operator ceremony instead:\n"
                "  manage.py bootstrap_single_operator_reviewer --username <you> "
                "--expires-days 14 --reason '<why>'\n"
                "It requires an interactive password challenge, a classified "
                "LOCAL_DEVELOPMENT environment, and it closes bootstrap permanently.")

        operator = self._active_superuser(opts["superuser"])

        # lock the singleton state for the whole precondition check + seed
        state = BootstrapState.objects.select_for_update().get(pk=1)
        if state.closed:
            raise CommandError(
                "bootstrap is permanently CLOSED for this environment. Use the documented "
                "--break-glass procedure if a re-seed is genuinely required.")
        if DecisionEvent.objects.filter(action__in=ROLE_MGMT_ACTIONS).exists():
            raise CommandError(
                "a protected role-management decision already exists — bootstrap is over.")
        now = timezone.now()
        if (ReviewerRoleAssignment.objects.exclude(grant_source=GRANT_BOOTSTRAP)
                .active_at(now).exists()):
            raise CommandError(
                "active non-bootstrap reviewer authority already exists; bootstrap is not "
                "appropriate.")

        User = get_user_model()
        try:
            user = User.objects.get(username=opts["username"])
        except User.DoesNotExist:
            raise CommandError(f"no user {opts['username']!r}. Create the account first.")
        if not user.is_active:
            raise CommandError(f"user {user.username!r} is inactive.")

        expires_at = now + timezone.timedelta(days=opts["expires_days"])
        if (ReviewerRoleAssignment.objects
                .filter(user=user, role=opts["role"]).active_at(now).exists()):
            raise CommandError(
                f"user {user.username!r} already holds an active {opts['role']}.")

        if not opts["yes"]:
            self.stdout.write(self.style.WARNING(
                f"BOOTSTRAP-grant {opts['role']} to {user.username!r} "
                f"(operator {operator.username!r}, expires {expires_at:%Y-%m-%d})."))
            if input("Type 'yes' to proceed: ").strip().lower() != "yes":
                raise CommandError("aborted.")

        profile, created = ReviewerProfile.objects.get_or_create(
            user=user, defaults={"display_name": opts["display_name"],
                                 "reviewer_enabled": True})
        if not created and not profile.reviewer_enabled:
            profile.reviewer_enabled = True
            profile.save()

        assignment = ReviewerRoleAssignment(
            user=user, role=opts["role"], granted_by=None, granted_at=now,
            expires_at=expires_at, grant_source=GRANT_BOOTSTRAP,
            grant_reason=opts["reason"].strip())
        try:
            assignment.save()
        except ValidationError as e:
            raise CommandError(f"refused: {e.messages}")

        self.stdout.write(self.style.SUCCESS(
            f"BOOTSTRAP granted {opts['role']} to {user.username!r} "
            f"(assignment #{assignment.pk}, operator {operator.username!r}). Bootstrap "
            "closes automatically on the first protected role-management decision."))

    # --- break-glass reopen -------------------------------------------------------
    def _break_glass(self, opts):
        if not getattr(settings, "BOOTSTRAP_BREAK_GLASS_ENABLED", False):
            raise CommandError(
                "break-glass is disabled. It requires BOOTSTRAP_BREAK_GLASS_ENABLED and is "
                "a deliberate, audited incident procedure.")
        operator = self._active_superuser(opts["superuser"])
        state = BootstrapState.objects.select_for_update().get(pk=1)
        # DIP-1A-BOOTSTRAP-CORR-2: this procedure was written for the two-person ceremony.
        # Reopening a single-operator closure has different consequences — it would allow a
        # second self-bootstrap on a chain that already contains one — so it needs its own
        # reviewed design and does NOT inherit this one. Refused without side effects:
        # break_glass_count is not incremented and the closure anchor is not cleared.
        anchor = state.closed_by_event
        if anchor is not None and bootstrap_registry.is_bootstrap_event(anchor):
            raise CommandError(
                "SINGLE_OPERATOR_BOOTSTRAP_REOPEN_REQUIRES_SEPARATE_REVIEW: this closure "
                "is anchored to a single-operator ceremony event "
                f"({anchor.event_id}). Reopening it is out of scope for this procedure; "
                "nothing was changed.")
        state.closed = False
        state.closed_at = None
        state.closed_by_event = None
        state.break_glass_count = state.break_glass_count + 1
        state.save()
        # CRITICAL, durable audit. It grants nothing; it records that the bypass was used.
        AuthorizationAudit.objects.create(
            user=operator, action="bootstrap_break_glass", result=RESULT_DENIED,
            reason_code=BREAK_GLASS_REASON, role_used="", endpoint="manage.py bootstrap",
            request_method="SERVICE",
            metadata={"severity": "CRITICAL", "operator": operator.username,
                      "break_glass_count": state.break_glass_count})
        self.stdout.write(self.style.WARNING(
            f"BREAK-GLASS: bootstrap re-opened by {operator.username!r} "
            f"(count={state.break_glass_count}). A CRITICAL audit record was written. This "
            "granted NO authority; run a normal bootstrap next if that is the intent."))
