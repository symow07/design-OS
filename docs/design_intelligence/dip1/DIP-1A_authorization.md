# DIP-1A-3 — authorization service, enforcement, and audit

## The decision: `authorize_actor(user, action, subject=None, at=None)`

One pure function turns a request into an `AuthorizationResult` (frozen). It **reads**
(authenticated user, persisted role assignments, canonical policy) and **never writes** —
persisting the attempt is a separate step, so a decision never depends on the database
being writable. The caller chooses **nothing**: not the actor id (`request.user.pk`), not
the active roles (persisted assignments), not `role_used` (policy selects it), not the
result. A request body `actor_id` or `role` is ignored by construction — the service never
reads the body.

**Deny by default**, fixed check order → stable reason code:

| order | reason_code | when |
|---|---|---|
| 1 | `UNAUTHENTICATED` | no authenticated user |
| 2 | `USER_INACTIVE` | `User.is_active` is false |
| 3 | `REVIEWER_PROFILE_MISSING` | no `ReviewerProfile` |
| 4 | `REVIEWER_DISABLED` | profile `reviewer_enabled` false |
| 5 | `ACTION_UNKNOWN` | action ∉ canonical `ACTIONS` |
| 6 | `NO_ACTIVE_ROLE` | no live role assignment |
| 7 | `SYSTEM_ADMIN_FORBIDDEN` | holds SYSTEM_ADMIN and the action is one it may never do (even alongside another unauthorized role) |
| 7 | `ROLE_NOT_AUTHORIZED` | otherwise no held role authorizes the action |
| — | `AUTHORIZED` | a role authorizes it |

`role_used` is chosen by the canonical **least-privilege-by-action-breadth** rule
(`select_role_used`), never row order or request input.

## Enforcement (server-side boundary)

Each protected endpoint maps to **exactly one** canonical action, declared in code —
never taken from the request. Three integration points, all sharing the service + audit:

- **`@require_reviewer_action(ACTION)`** — function views (incl. DRF `@api_view`).
- **`ReviewerActionMixin`** — class-based views (sets `required_action`).
- **`ReviewerActionPermission`** — DRF `BasePermission` for read/query gates.

**Fail-closed on the allowed path.** The decorator/mixin run the action and write the audit
row inside **one `transaction.atomic()`**; if the audit cannot be written the whole thing
rolls back and nothing commits — an allowed decision never commits unaudited. (Verified by
injecting an audit-write failure and asserting the action's side-effect row is absent.) A
bare permission runs outside the view transaction, so decision-class side-effecting
endpoints use the decorator/mixin; the permission is for gates with no side effect.

**Denials** are audited best-effort: a failed audit write is logged (no internals leaked)
and the request stays denied. **No audit failure ever turns a denial into an allow.**

**Unauthenticated attempts are audited** (user = NULL, `UNAUTHENTICATED`). Protected views
set `permission_classes = [ReviewerActionPermission]` explicitly so the whole pipeline runs
and records the attempt, rather than being rejected upstream by the global `IsAuthenticated`.

## `AuthorizationAudit`

Append-only evidence, written server-side only. `PROTECT` user FK (nullable **only** for
unauthenticated). Fields: action, subject_type/id, result, reason_code, active_roles,
authorizing_roles, role_used, selection_rule, endpoint, request_method, correlation_id,
source_ip, user_agent, metadata, created_at. **Never stored:** passwords, cookies, CSRF
tokens, auth headers, tokens, request bodies, evidence documents, raw exception strings.

- **Append-only** through the app: the manager refuses `update()`/`delete()`, and `save()`
  refuses to rewrite a loaded row (not just `.update()`). A correction is a new row.
- **DB CHECK** `aa_allow_iff_role_used`: an ALLOWED row must name a `role_used` and read
  `AUTHORIZED`; a DENIED row must not — a malformed row that bypassed the service is
  refused by the database.
- **correlation_id** is validated and capped **at record time** (the request-id middleware
  honours an inbound `X-Request-ID` with no length cap; oversized/invalid values are
  discarded and a fresh UUID stored, never truncated-and-kept).
- **source_ip** is off by default (`AUTHORIZATION_AUDIT_RECORD_IP=False`); when enabled,
  `X-Forwarded-For` is trusted **only** from `AUTHORIZATION_TRUSTED_PROXIES`, else the
  direct `REMOTE_ADDR`. A forged XFF from a non-trusted peer is ignored.
- **user_agent** capped (400).
- Registered **read-only** in admin (reuses the 1A-2 `_ReadOnlyAdmin`).

> **Honest limitation.** `AuthorizationAudit` is **outside** the signed DecisionEvent chain
> (1A-4). A direct database superuser can still mutate this table, and that is **not**
> cryptographically detectable in 1A-3. Stronger tamper evidence (the HMAC hash chain)
> arrives in 1A-4.

## CSRF / SessionAuthentication

Unsafe protected operations are POST, never GET, never `csrf_exempt`, and keep DRF
`SessionAuthentication` (CSRF enforced). Tests run with `enforce_csrf_checks=True` and
prove: missing token → refused **before** authorization (no audit row); valid token but
unauthorized role → denied **and** audited; valid token + authorized role → succeeds.

## Policy-drift check

`accounts.policy.E003`: every action a protected endpoint registers must be a known
canonical action. Scoped to the **DIP reviewer policy only** — the legacy pipeline
Designer/Reviewer/Admin Group permissions are a separate system, untouched. The check
nudges the URLconf to load so the endpoint registry is populated before it inspects it.

## Verified

- Full Django suite **653 passed / 1 skipped**; ruff clean; no migration drift.
- Reason codes exercised end-to-end: all 8 denial codes + `AUTHORIZED`.
- Fail-closed rollback proven (action absent when audit write fails); denial-audit failure
  still denies.
- CSRF: 3 enforced-mode tests (missing / valid-unauthorized / valid-authorized).
- Migration `0002_authorizationaudit`: creates only `accounts_authorizationaudit` (+ its
  indexes, CHECK, and additive FK to `auth_user`); alters no existing table; forward /
  reverse-to-0001 / re-apply verified with users and profiles preserved.
- Still absent (asserted): no `DecisionEvent` / `DecisionChainHead` model, exactly two
  accounts migrations, no retrieval / auto-use / permission-grant surface.

## NOT in 1A-3 (→ 1A-4/1A-5)

DecisionEvent, DecisionChainHead, HMAC event append, protected role-grant/revoke service,
dual-control activation, approval workflows, permission grants, retrieval, automatic use,
review UI.
