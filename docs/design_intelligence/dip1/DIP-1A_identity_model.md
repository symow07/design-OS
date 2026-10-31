# DIP-1A-2 — reviewer identity, roles, and role resolution

Extends Django's `auth.User` **by composition**. No `AUTH_USER_MODEL` swap; `request.user.pk`
stays the authoritative actor id. Two new tables attach *reviewer meaning* to existing
accounts; neither stores credentials, and neither is a second notion of "active".

## The two models

**`ReviewerProfile`** — participation in reviewer workflows. `reviewer_enabled` **defaults
to False**: creating a profile does not confer authority. Distinct from `User.is_active`
(the account). Either being false ⇒ no roles.

**`ReviewerRoleAssignment`** — one grant of one role to one user, time-bounded.
Append-only in spirit: revocation writes `revoked_at` / `revoked_by` / `revocation_reason`
onto the row; a re-grant is a **new row**. Nothing is deleted, because the question after
an incident — *who could do this, and when?* — is answerable only if history survives.
There is deliberately **no `(user, role)` unique constraint** (it would forbid grant →
expire → re-grant) and **no stored `is_active` flag** (a flag needs a maintainer, and the
maintainer is a cron job you forgot to run).

The role vocabulary is **not** redefined or bound as `choices`. `tools/dip0c/authz.py` is
the single policy source; the field carries no `choices` because `makemigrations` would
freeze that literal into `0001` and CI's `--check` would fail the day `authz.ROLES`
changes — the migration would *become* the drifting copy this design exists to avoid.
Validity is enforced in `clean()` against the live policy.

> **Policy location (decoupled).** The canonical authorization policy lives at
> `apps/accounts/authz_policy.py` — a **pure-stdlib, Django-free** module inside the
> deployable app package. `tools/dip0c/authz.py` is now a thin wrapper that re-exports it
> (adding only DIP-audit state glue). A deploy needs nothing beyond `bbrose_design_os/`;
> the production app never imports the `tools/` package. A policy system check
> (`accounts.policy.E001/E002`) fails the deploy loudly if the module is unreachable or
> degenerate. See `DIP-1A_policy_decoupling.md`.

## `active_roles(user, at=None)` — the resolver

Answers exactly one question — *which roles are live at `at`?* — and **authorizes
nothing**. The policy consultation belongs to the authorization service (1A-3); keeping
them apart means a resolver bug can only fail to grant, never grant.

**Point-in-time, and honest about the past.** Revocation is a boundary, not retroactive
erasure: a role revoked at `T_r` *was* active for every instant before `T_r`. The
queryset excludes a revoked row only when `at >= T_r` (`revoked_at__gt=at`). `at` is
injectable for deterministic expiry in tests and truthful audit queries. **No
cross-request cache** — a revocation must bite on the very next request.

**Fails closed on every axis:** unauthenticated · inactive user · missing profile ·
disabled profile · not-yet-started · expired · revoked · or a stored role no longer in the
policy (ignored, not deleted — fail closed *and* keep the record). Overlapping live grants
of one role collapse to one authority; `overlapping_active_assignments()` reports them so
1A-5 can refuse to *create* new overlaps.

## Database constraints (defeat a `clean()` bypass)

`save()` runs `full_clean()`, but a `bulk_create` / raw SQL path skips it — so the
invariants are also CHECK constraints, refused at the layer a stray script cannot argue
with:

| constraint | refuses |
|---|---|
| `rra_expires_after_granted` | `expires_at <= granted_at` |
| `rra_revoked_not_before_granted` | `revoked_at < granted_at` |
| `rra_revoked_requires_revoker` | a revocation with no revoker (an event with no actor) |
| `rra_granter_required_unless_bootstrap` | a non-bootstrap grant with no granter |

`clean()` additionally refuses a **future** `revoked_at` (a scheduled revocation is exactly
the deferred-maintenance flag this model rejects) and a blank grant/production-revocation
reason.

FKs (`user`, `granted_by`, `revoked_by`) are **`PROTECT`**: a user named on any assignment
cannot be deleted, so review history cannot be erased by removing an account.

## Bootstrap — breaking the chicken-and-egg

Every production grant must name a granter, but the first grant has no prior reviewer. The
`bootstrap_reviewer_role` management command is the **only** sanctioned writer of
`grant_source=BOOTSTRAP` / `granted_by=NULL` (the one combination the DB permits without a
granter). It is deliberately explicit — required `--role`, `--expires-days`, `--reason` —
refuses a duplicate active grant, refuses an inactive/unknown user, and writes through
`save()` so every other rule still applies. It seeds 1A-5's first operator; it is not how
ongoing grants happen.

## Admin

`ReviewerProfile` and `ReviewerRoleAssignment` are registered **read-only** (no add /
change / delete, all fields read-only). They are security evidence; granting and revoking
happen through audited services, never a form that records neither who nor why.

## Migration safety (verified)

`0001_initial` uses `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`. Verified:
`makemigrations --check` reports no drift · pure `CreateModel` + indexes + CHECK
constraints + PROTECT FKs (no data migration, no destructive op) · applies cleanly
alongside the 26 existing migrations · reverses to `zero` · re-applies idempotently · all
four CHECK constraints present in the generated DDL · deploy check green with a key
configured.

## Explicitly NOT in 1A-2

No protected endpoints/decorators, no `AuthorizationAudit`, no `DecisionEvent` or signed
chain head, no production grant/revoke service, no dual-control workflow, no UI, no
approval/activation paths. Those are 1A-3 → 1A-5.
