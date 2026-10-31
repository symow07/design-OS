# DIP-1A — authorization-policy decoupling

## Why

DIP-1A-2 made the Django accounts app store role *assignments* against the authorization
policy that had lived in `tools/dip0c/authz.py` since DIP-0C3b2. To reach it, settings put
the repository root on `sys.path`. That made the **audit tool a production boot dependency**:
the Django app would not start unless the `tools/` package shipped alongside it. Acceptable
as a bridge, wrong as a permanent boundary.

## What changed

**The canonical policy now lives inside the deployable app package:**
`apps/accounts/authz_policy.py`. It is pure standard library — no Django, no database, no
filesystem, no `materials/`, no `tools/`. It is safe to import at Django startup, during
migrations, in CI, and by standalone audit tooling.

`tools/dip0c/authz.py` is now a **thin compatibility wrapper**. It re-exports the canonical
policy verbatim (`from apps.accounts.authz_policy import *`, against an explicit `__all__`)
and keeps only the DIP-audit-specific glue that depends on `tools.dip0c.config` and has no
place in a pure policy module:

- `PARSER` — the tool's identity string;
- `STATE_ACTION` / `action_for_state()` — ownership/licence **states** (a DIP-ledger
  concept) mapped to the action confirming them requires;
- `policy_document()` — the canonical policy plus the state map, output **unchanged** so
  existing DIP reports (e.g. `run_c3b2`) serialise byte-for-byte as before.

**Import direction:** the audit tool depends on the app's canonical policy; the production
app never imports `tools/`. The wrapper adds the app package to `sys.path` on the
**audit side** only, so the DIP tools keep running standalone from the repo root.

The `REPO_ROOT` `sys.path` insert was **removed** from settings. Deploying
`bbrose_design_os/` is now sufficient.

## There is exactly one policy

The four Django consumers (`models.py`, `checks.py`, the bootstrap command, tests) import
`apps.accounts.authz_policy`. Every DIP consumer imports the wrapper, which *is* the same
objects. Tests assert the wrapper's `POLICY` **is** (identity, not equality) the canonical
`POLICY`, so a second definition cannot silently appear.

## Deterministic role selection (added here, used by 1A-3)

The canonical module gained `select_role_used(action, active_roles)` and
`authorizing_roles(action, roles)`. When an actor holds several roles that all authorize an
action, `role_used` is chosen by a fixed, policy-defined rule —
**least privilege by action breadth**: the authorizing role that can perform the fewest
actions overall wins (ties broken by canonical `ROLES` order). So a legal determination is
attributed to `LEGAL_REVIEWER` rather than a `BRAND_ADMIN` who merely also qualifies, and a
revocation to the reduce-only `SYSTEM_ADMIN`. Never row order, set iteration, alphabetical
accident, or request input. Rule id: `least_privilege_by_action_breadth/1.0`.

## Verified

- Canonical module imports no `tools` and no `django` (AST-asserted); only `__future__` at
  module scope.
- Full Django suite (621 passed) runs with the repo root **not** on `sys.path` — empirical
  proof the app boots and authorizes without the `tools/` package.
- DIP authz-consumer suites green through the wrapper (238 passed incl. the new
  decoupling tests); `policy_document()` shape unchanged.
- No migration drift; deploy check green; ruff clean.
- Behaviour preserved exactly: same roles, actions, mappings, `SYSTEM_ADMIN_FORBIDDEN`,
  and `may`/`authorize` results.
