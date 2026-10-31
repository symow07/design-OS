"""Single-operator initial reviewer ceremony (DIP-1A-BOOTSTRAP-CORR-2).

`--username admin` proves nothing: anyone with shell access can type it. This command
therefore requires an **interactive password challenge** against Django's authentication
backend before it opens a transaction, and records the resulting basis in the signed event
as `DJANGO_PASSWORD_CHALLENGE_LOCAL_CLI` — never claiming that a username argument
authenticated anyone.

The password is read with `getpass` (never echoed, never an argument, never an environment
variable), used once, and dropped. It is never logged, audited, put in an exception message,
written to the event, or captured in a test snapshot.

Never exposed through the web.
"""
from __future__ import annotations

import getpass
import sys

from django.contrib.auth import authenticate, get_user_model
from django.core.management.base import BaseCommand, CommandError

from ... import bootstrap_registry as reg
from ...bootstrap_ceremony import CeremonyError, perform_single_operator_ceremony
from ...bootstrap_environment import EnvironmentClassificationError


class Command(BaseCommand):
    help = ("Single-operator LOCAL DEVELOPMENT bootstrap of a time-limited "
            "DESIGN_REVIEWER. Requires an interactive password challenge; closes "
            "bootstrap permanently.")

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True,
                           help="The account you will authenticate as AND grant to.")
        parser.add_argument("--expires-days", type=int, required=True,
                           help=f"Days until expiry (max {reg.MAX_EXPIRY_DAYS}).")
        parser.add_argument("--reason", required=True,
                           help="Why this role is being held (recorded in the event).")
        parser.add_argument("--role", default=reg.ALLOWED_BOOTSTRAP_ROLES[0],
                           help="Must be DESIGN_REVIEWER.")
        parser.add_argument("--display-name", default="")
        parser.add_argument("--dry-run", action="store_true",
                           help="Report readiness without authenticating or writing.")

    def handle(self, *args, **opts):
        if opts["dry_run"]:
            return self._dry_run(opts)
        user = self._password_challenge(opts["username"])
        try:
            result = perform_single_operator_ceremony(
                authenticated_user=user, role=opts["role"],
                expires_days=opts["expires_days"], reason=opts["reason"],
                account_control_basis=reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE,
                display_name=opts["display_name"])
        except (CeremonyError, EnvironmentClassificationError) as exc:
            raise CommandError(str(exc)) from None
        if result.status == "ALREADY_COMPLETED":
            self.stdout.write(self.style.WARNING(
                f"ALREADY_COMPLETED — ceremony event {result.event_id} already exists and "
                "reconciles exactly. Nothing was written."))
            return
        self.stdout.write(self.style.SUCCESS(
            f"SINGLE-OPERATOR ceremony complete for {result.username!r}: {result.role} "
            f"until {result.expires_at:%Y-%m-%d}, event {result.event_id}. Bootstrap is "
            "now permanently CLOSED. This was NOT dual control and the signed event says "
            "so."))

    # --- account control ----------------------------------------------------------
    def _password_challenge(self, username):
        """Prove the operator controls the account. Fails closed, writes nothing."""
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise CommandError(
                "an interactive terminal is required: this ceremony must not run "
                "unattended, and the password may not come from an argument, a pipe or an "
                "environment variable.")
        User = get_user_model()
        target = User.objects.filter(username=username).first()
        if target is None:
            raise CommandError(f"no account {username!r}.")
        self.stdout.write(
            f"Authenticate as {username!r} to perform a SINGLE-OPERATOR bootstrap. "
            "This is not dual control.")
        try:
            password = getpass.getpass("Password: ")
        except (EOFError, KeyboardInterrupt):
            raise CommandError("aborted; nothing was written.") from None
        try:
            authenticated = authenticate(username=username, password=password)
        finally:
            del password                      # dropped immediately, however we exit
        if authenticated is None:
            # deliberately not distinguishing bad password from backend refusal
            raise CommandError("authentication failed; nothing was written.")
        if authenticated.pk != target.pk:
            raise CommandError(
                "the authenticated account differs from the selected account; nothing was "
                "written.")
        if not authenticated.is_active:
            raise CommandError("account is inactive; nothing was written.")
        if not authenticated.is_superuser:
            raise CommandError("account is not a superuser; nothing was written.")
        return authenticated

    # --- dry run ------------------------------------------------------------------
    def _dry_run(self, opts):
        """Readiness only. Never prompts for, or touches, a password."""
        from ...bootstrap_preflight import build_ceremony_preflight
        report = build_ceremony_preflight(
            username=opts["username"], role=opts["role"],
            expires_days=opts["expires_days"])
        for line in report["lines"]:
            self.stdout.write(line)
        self.stdout.write(
            self.style.SUCCESS("READY — the only remaining step is the interactive "
                               "password challenge.")
            if report["ready"] else
            self.style.WARNING(f"NOT READY: {', '.join(report['blocking'])}"))
