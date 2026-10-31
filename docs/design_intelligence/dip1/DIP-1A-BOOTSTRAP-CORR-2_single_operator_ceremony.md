# DIP-1A-BOOTSTRAP-CORR-2 — Single-Operator Initial Reviewer Ceremony

**Implemented and verified. Not executed.** No ceremony has been run, no role granted, no
DecisionEvent appended. `BootstrapState` is still open and the chain is still at genesis.

## Why this exists

`grant_reviewer_role` is restricted to `BUSINESS_OWNER`/`BRAND_ADMIN` and its self-elevation
guard forbids granting to the acting user. A protected grant therefore needs **two distinct
authenticated humans**. In a genuinely single-operator environment there were only two ways
forward, and both were dishonest:

* a **second account owned by the same person** — satisfies the guard's letter, writes a
  false two-party trail into an immutable record, and is undetectable afterwards;
* the **legacy direct bootstrap** — seeds a reviewer without recording any protected
  role-management event, so `BootstrapState.closed` stays `False` forever and only an
  environment flag stands between the deployment and a repeat.

This ceremony is the third option. It is *visibly* weaker than dual control and says so in
its own signed payload. **An honest weak record beats a dishonest strong one.**

## What it is, and is not

Single operator · local development only · **not dual control** · password-confirmed Django
account · time-limited `DESIGN_REVIEWER` only · no authority-tree bootstrap · permanent
in-database closure · not reachable from the web.

## Account control — a username argument proves nothing

`--superuser admin` proves only that someone can type. The command requires an
**interactive password challenge** before any transaction opens: TTY required, `getpass`
(never echoed, never an argument or environment variable), `authenticate()` against the
Django backend, and the authenticated user must *be* the selected user, active, and a
superuser. The password is dropped in a `finally` block and never reaches a log, an audit
row, an exception message, the event payload, or a test snapshot.

The signed basis is recorded as `DJANGO_PASSWORD_CHALLENGE_LOCAL_CLI`. The event never
claims that a username argument authenticated anyone.

## Separate event registry

`bootstrap_initial_reviewer_role` lives in [`bootstrap_registry.py`](../../../bbrose_design_os/apps/accounts/bootstrap_registry.py),
**not** in `authz.ACTIONS` and **not** in any role policy. Consequences, each covered by a
test: `authorize_actor` denies it with `ACTION_UNKNOWN`; `append_decision` rejects it in
`_validate_event_inputs`; no role authorizes it; it is absent from `PROTECTED_ACTIONS` so no
endpoint can reach it. `role_used` is the sentinel `BOOTSTRAP_OPERATOR`, which is **not** a
member of `authz.ROLES` — a reader seeing it knows no role authorized this event, because no
such role exists.

The only producer is `append_bootstrap_initial_reviewer_event`, which is guarded by a private
capability object and hard-codes the action, sentinel and payload schema. It cannot emit any
other event, so there is no reusable "skip authorization" switch to widen later. It shares
`_sign_and_insert` with the ordinary append, so the ceremony gets no alternate crypto — only
an alternate authorization story, stated openly.

## Environment classification

`DEBUG=True` plus a loopback database does **not** mean local: a tunnelled production
database answers on `127.0.0.1` identically. All of these must hold —

`BOOTSTRAP_ENABLED` · `BOOTSTRAP_SINGLE_OPERATOR_ENABLED` (both default `False`, and
independent) · `DEBUG=True` · `ENVIRONMENT == "LOCAL_DEVELOPMENT"` · database host is a
loopback address or UNIX socket · database **name** in `LOCAL_DEVELOPMENT_DATABASES` · no
production marker setting present.

The name is the discriminator the endpoint cannot provide. Four Django system checks
(`accounts.bootstrap.E010`–`E013`) fail at startup if the flag is set outside a classified
local environment, so a production config carrying it is a startup failure even if the
command is never run.

## One-shot preconditions

Both flags · classified environment · password challenge passed · active superuser · actor
== target · chain verifies · chain at genesis · zero DecisionEvents · zero
`ReviewerRoleAssignment` rows **across the database** · bootstrap open · `break_glass_count
== 0` · no prior ceremony event · role in an allow-list of exactly `("DESIGN_REVIEWER",)` ·
explicit expiry ≤ 30 days · non-empty bounded reason · zero operational permissions.

The role allow-list means a role added to `authz.ROLES` in future cannot enter the ceremony
through a permissive default — it would have to be added here deliberately.

## Lock order and concurrency

Following the established role-lifecycle order (target rows → chain head → bootstrap state):

1. `select_for_update` the target **User** row — serialises ceremonies against the same account
2. lock that user's `ReviewerProfile` and `ReviewerRoleAssignment` rows
3. lock `DecisionChainHead` — serialises ceremonies against **different** accounts
4. lock `BootstrapState`
5. re-check **every** database precondition under the locks (the preflight copy is a
   courtesy; this one is the guarantee)
6. write

Measured: two ceremonies against the same account and two against different accounts each
produce exactly one event, one assignment and one closure, with no deadlock and no fork.

## Atomic write sequence

One outer `transaction.atomic`: create/enable profile → insert the time-bound assignment →
append the signed event → close `BootstrapState` → anchor closure to the event → write the
CRITICAL audit row. Any failure rolls back all of it — tested by inducing failure at the
append and audit steps and asserting no profile, no assignment, no event, an open state, and
a chain that still verifies.

## Assignment provenance

`grant_source = BOOTSTRAP_SINGLE_OPERATOR` — a **distinct** source, never the generic
`BOOTSTRAP`, so the row alone distinguishes a single-operator self-bootstrap from a
two-person pre-ledger seed. `granted_by` is the authenticated actor, **not null**: this is an
explicit self-bootstrap and the actor stays nameable through the `PROTECT` FK. The distinct
source and the signed event, not a null granter, are what mark it as extraordinary.

The normal self-elevation guard in `grant_reviewer_role` is **untouched**, and a test proves
the bootstrapped `DESIGN_REVIEWER` cannot grant anything to anyone.

## Closure anchoring

`closed=True`, `closed_at`, and `closed_by_event` (FK, `PROTECT`) are set in the same
transaction as the grant. The `PROTECT` constraint means the anchoring event cannot be
deleted while it anchors the closure — closure rests on an immutable signed record, not on a
boolean anyone could flip. Re-enabling either flag, or restarting the application, cannot
reopen it.

A repeat invocation reports `ALREADY_COMPLETED` and writes nothing — but **only** when the
event, assignment and state reconcile exactly. Any mismatch reports
`BOOTSTRAP_STATE_INCONSISTENT` and fails closed.

## Chain verification

The bootstrap event is routed to its **own** verifier
([`bootstrap_verification.py`](../../../bbrose_design_os/apps/accounts/bootstrap_verification.py)),
which is *stricter* than the general path, not laxer: everything the general path would have
inferred from a role must instead be proven against the payload, the assignment row and the
bootstrap state — sentinel, actor==target, `single_operator`, `dual_control`, granted role,
environment classification, account-control basis, expiry bound, prior/resulting state, the
matching assignment's granter/timestamps/expiry/reason, the enabled profile, and the closure
anchor.

Rejected: the sentinel on any other action (checked for **every** event, so it cannot be
borrowed), a fabricated `authz_snapshot` on a bootstrap event, actor/target mismatch, a
forbidden role, a missing or mismatched assignment, an open state after the ceremony, and
more than one ceremony event. Ordinary events are verified exactly as before —
role/snapshot checks were **not** made globally optional.

Whole-chain consistency adds `BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN` for the directions a
per-event check cannot see: an assignment with no signed event, a closure anchored to an
unrelated action, a ceremony event with an open state.

## Break-glass boundary

The existing break-glass procedure **refuses** to reopen a closure anchored to a
single-operator ceremony event:
`SINGLE_OPERATOR_BOOTSTRAP_REOPEN_REQUIRES_SEPARATE_REVIEW`. It does not increment
`break_glass_count` and does not clear the anchor. Reopening such a closure would permit a
second self-bootstrap on a chain that already contains one; that needs its own reviewed
design and deliberately does not inherit a procedure written for the two-person ceremony.

## Legacy direct bootstrap: closed

`bootstrap_reviewer_role --role DESIGN_REVIEWER` now **refuses**, naming the replacement
command in the error. The two-person path remains available for the roles it legitimately
seeds (e.g. `BRAND_ADMIN`, which can then use the protected role service — recording a
DecisionEvent and closing bootstrap). The rejected Path A is not left available as an
undocumented alternative.

## Migration

`0006_single_operator_bootstrap_source` — `AlterField` on `grant_source` **choices only**.
`sqlmigrate` output is `-- (no-op)`: choices are Django-level validation, not a database
constraint. `BootstrapState.closed_at` and `closed_by_event` (FK, `PROTECT`) already existed
from `0005`, so the closure anchor needed no schema change. A committed migration-executor
test proves forward, rollback and re-application preserve every existing user, profile,
assignment and bootstrap-state row, and checks the live column definition is unchanged.

## Security limitations (stated, not solved)

* **Full-database rollback.** A restore of both the database and the chain head to a
  pre-ceremony snapshot is indistinguishable from an environment that never ran the
  ceremony. No in-database mechanism can detect that; only an external anchor could, and
  there is none. Consistency checking detects the *partial* cases (event without state,
  state without event, assignment without event) — not the complete one.
* **Local trust.** Anyone who can run `manage.py` on the machine and knows the account
  password can perform the ceremony. That is the honest scope of a local development
  affordance, and the reason it is confined to one time-bounded `DESIGN_REVIEWER`.
* **Audit `reason_code` reads `AUTHORIZED`** because the table's check constraint requires
  exactly that for an `ALLOWED` row. The true basis is in `metadata`
  (`SUPERUSER_LOCAL_BOOTSTRAP_NOT_ROLE_POLICY`) and `role_used` is the sentinel, so nothing
  reads as a role decision.

## Later multi-person governance is unchanged

`GRANT_REVIEWER_ROLE` remains `BUSINESS_OWNER`/`BRAND_ADMIN` only; the self-elevation guard
is untouched; the ceremony's output is one time-bounded `DESIGN_REVIEWER` who can grant
nothing. Every subsequent role change still requires two distinct authenticated humans —
which is precisely why this ceremony cannot become a path to a second reviewer.

## Verification

Full suite green; ruff clean; system checks pass; migration drift zero. 39 new tests cover
authentication, environment, ceremony preconditions, atomicity, verification, legacy-path
closure, break-glass refusal, projector separation, concurrency and the migration.
