"""Startup surface for migration drift on a DECLARED local machine.

`ops.migration_guard` asks for a startup check. The measurement it needs has
existed since the node opened — `apps.core.health.migration_state`, which
names the unapplied migrations and distinguishes "behind" from "cannot read".
What did not exist was anything that *reports* it at startup on this machine,
and the node's own record says so: "no startup surface reports drift on THIS
machine". This module is that surface and nothing more.

WHY IT IS GATED ON `ENVIRONMENT`, AND WHY THAT IS NOT THE SAME LOCK AS THE ONE
THAT MADE `apps/dielines/checks.py` SILENT HERE. Two refusals are already on
the record and both survive:

  * It is NOT wired into `run_health_checks()`. /healthz returns 503 when any
    value is not "ok"/"eager" (apps/core/views.py), so a migration entry there
    would pull a service out of rotation during exactly the rolling deploy
    where the new code is live and `migrate` has not run yet. Drift is a
    correctness signal for whoever is about to trust the schema; it is not a
    liveness signal. `MigrationStateTests.test_migration_state_is_not_wired_
    into_healthz` asserts that and this module does not weaken it.

  * It is NOT unconditional. CI never applies migrations — measured
    2026-08-22, `.github/workflows/ci.yml` contains the word `migrate` zero
    times and sets `ENVIRONMENT` zero times — so its database is legitimately
    unmigrated and an ungated check would warn on every CI run. A warning that
    fires on every run is noise, and noise is how a real one gets missed.

  * It is NOT gated on `STANDARD_VECTOR_PACKAGING_PIPELINE`. That flag is what
    made the dielines migration arm silent on this machine: `check_standard_
    pipeline_activation` returns `[]` at its first two lines, before
    `ENVIRONMENT` is ever read. A packaging feature flag is the wrong question
    to ask about whether the schema is current, and tying the two together is
    why a real unapplied migration sat on the dev database with nothing
    reporting it. [The clean-up of 2026-10-04, his Q1 "remove the dormant
    packaging flow": the flag and that dielines arm left with the structure-
    confirmation flow; the reason this surface is gated on `ENVIRONMENT`
    alone stands.]

WHY `Warning` AND NOT `Error`. The first version of this paragraph said:
"`migrate` skips system checks in Django 4.2 (`requires_system_checks = []`),
so an Error would not deadlock the command that fixes the condition — but it
WOULD stop `runserver`, `shell` and every other management command."
BOTH HALVES OF THAT WERE FALSE, and it is quoted rather than deleted because
it was the stated reason for a design decision that happens to be correct.
Measured 2026-08-22 against the installed Django 4.2:

  * `requires_system_checks = []` is set on `shell`, `migrate`, `check` AND
    `runserver` alike. It discriminates NOTHING. What actually decides is
    whether the command calls `self.check()` itself: `migrate` does, at
    `migrate.py:100`, `self.check(databases=[database])`, at the TOP of
    `handle()` before a single operation is applied; `check` does at
    `check.py:76`; `runserver` does at `runserver.py:133`. `shell` does not,
    and is the only one of the four that does not.
  * So `migrate` DOES run this check — verified with `manage.py migrate
    --plan`, which printed W001 and then the planned operations.
  * Which INVERTS the argument. An `Error` here would block exactly the
    command that fixes the condition: `self.check()` raises
    `SystemCheckError` on any Error, before `migrate` applies anything, so a
    behind database would refuse to be migrated because it is behind. And an
    Error would NOT stop `shell`, which never runs checks at all.
  * PRECISION ADDED BY A SECOND AUDIT, because the bullet above first said
    "deadlock" flatly and that was one word too strong. `self.check()` sits
    behind `if not options["skip_checks"]` at `migrate.py:99`. Measured:
    `manage.py migrate --plan --skip-checks` printed no W001 at all. So an
    Error would block the DEFAULT invocation — `manage.py migrate`, which is
    what the hint below tells people to run and what anyone actually types —
    and a flag escapes it. That is a bad enough trap to justify `Warning`
    and it is not an inescapable deadlock. The distinction is kept because
    "deadlock" invites the reply "then just pass --skip-checks", and the real
    answer is that a developer hitting this would not know that yet.
  * A THIRD AUDIT CORRECTED THE BULLET ABOVE, which had claimed
    `--skip-checks` "is a documented public flag on every command
    (`base.py:129`)". BOTH HALVES WRONG, and quoted rather than deleted:
    `base.py:129` is the `"--skip-checks"` string inside
    `DjangoHelpFormatter.show_last` — help ORDERING, not registration.
    Registration is `base.py:361-366` and is gated by
    `if self.requires_system_checks:`. Measured in this project's registry:
    23 of 62 commands have that attribute falsy and therefore never get the
    flag — `shell --skip-checks` and `check --skip-checks` both answer
    `error: unrecognized arguments`. `migrate` has it for one reason only:
    it re-adds the argument itself at `migrate.py:23-28`.
  * WHICH IS THE JOKE ON THIS WHOLE DOCSTRING. The headline three bullets up
    says `requires_system_checks = []` "discriminates NOTHING". It does
    discriminate — just not the thing it was originally cited for. It is
    exactly what decides whether `--skip-checks` exists on a command. Having
    demolished the attribute's relevance to *running* checks, this file then
    leaned on a consequence of that same attribute without noticing. It is
    still true that the attribute does not decide whether checks run.
  * AND THE ESCAPE IS WIDER THAN "one flag" IN THE OTHER DIRECTION:
    `call_command("migrate")` sets `skip_checks=True` by default whenever the
    caller does not pass it (`management/__init__.py:191-192`), so every
    programmatic invocation escapes too. The trap is real for a human typing
    `manage.py migrate`, and only for them.

The decision stands and is load-bearing for a stronger reason than the one
originally given. The check exists to be read, not to stop work.

WHY AN UNREADABLE DATABASE IS NOT SILENT. This module was written in the
tranche that documented `git status --short <absent-path>`: warning on stderr,
nothing on stdout, exit 0, which reads as "clean". Returning `[]` when the
state could NOT be determined would be the same shape — silence claiming
"no drift" when the honest answer is "no answer". So `unknown:` gets its own
id and its own sentence, and silence from this check means exactly one thing:
the database was read and it is current.
"""
from __future__ import annotations

from django.conf import settings
from django.core.checks import Warning, register

from apps.core.health import migration_state

MIGRATION_DRIFT = "core.migrations.W001"
MIGRATION_STATE_UNREADABLE = "core.migrations.W002"

_LOCAL = "LOCAL_DEVELOPMENT"


def _declared_local() -> bool:
    """The environment must DECLARE itself — never inferred from DEBUG or from
    a loopback database address, on the same rule as apps/dielines/checks.py
    and apps/accounts/checks.py. A tunnelled production database also answers
    on localhost."""
    return str(getattr(settings, "ENVIRONMENT", "UNCLASSIFIED")) == _LOCAL


@register("core")
def check_local_migration_drift(app_configs, **kwargs):
    if not _declared_local():
        return []

    state = migration_state()
    if state == "ok":
        return []

    if state.startswith("unknown: "):
        return [Warning(
            "The migration state of the local development database could not "
            f"be read: {state[len('unknown: '):]}",
            hint="This is NOT the same condition as a behind database and "
                 "`migrate` will not fix it — check the database is running "
                 "and reachable. Reported rather than passed over in silence, "
                 "because a check that says nothing when it cannot answer is "
                 "indistinguishable from one saying the schema is current.",
            id=MIGRATION_STATE_UNREADABLE)]

    return [Warning(
        f"The local development database is behind the migrations on disk — "
        f"{state}",
        hint="Run `venv/bin/python manage.py migrate`. Every model read "
             "against this database until then is reading a schema older than "
             "the code. Shown only because ENVIRONMENT=LOCAL_DEVELOPMENT is "
             "declared; CI never migrates and is never warned.",
        id=MIGRATION_DRIFT)]
