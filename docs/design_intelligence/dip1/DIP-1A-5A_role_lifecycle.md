# DIP-1A-5A — protected role lifecycle and bootstrap closure

Granting, revoking, enabling and disabling reviewer authority are **protected security
decisions**. Each authorizes the acting user, mutates the role/profile state, and appends a
signed DecisionEvent — atomically, so the persisted state and the ledger can never diverge.

## Canonical policy additions

Four actions join `apps/accounts/authz_policy.py` (the wrapper re-exports them; a test
asserts parity):

| action | roles | note |
|---|---|---|
| `grant_reviewer_role` | BUSINESS_OWNER, BRAND_ADMIN | appointing authority — SYSTEM_ADMIN forbidden |
| `enable_reviewer_profile` | BUSINESS_OWNER, BRAND_ADMIN | conferring participation — SYSTEM_ADMIN forbidden |
| `revoke_reviewer_role` | BUSINESS_OWNER, BRAND_ADMIN, SYSTEM_ADMIN | reduction — SYSTEM_ADMIN may pull the brake |
| `disable_reviewer_profile` | BUSINESS_OWNER, BRAND_ADMIN, SYSTEM_ADMIN | reduction |

Granting/enabling are in `SYSTEM_ADMIN_FORBIDDEN`: administrative power is not the
authority to appoint reviewers.

## Services — `apps/accounts/role_services.py`

`grant_reviewer_role`, `revoke_reviewer_role`, `enable_reviewer_profile`,
`disable_reviewer_profile`. The caller supplies the **target**, requested role, expiry and
reason — **never** the acting actor id, `role_used`, active roles, or an authorization
result. The acting user comes from the authenticated caller.

Each service:

1. authorizes the acting user (canonical 1A-3 service);
2. **on denial, writes a best-effort DENIED audit and raises — OUTSIDE any transaction**,
   so the audit survives the non-mutation (the 1A-3 discipline);
3. only when allowed, opens **one** `transaction.atomic()`;
4. locks the target rows, validates, appends the protected DecisionEvent, mutates the
   assignment/profile, closes bootstrap, and writes the ALLOWED audit **inside** the atomic
   — an audit-write failure rolls the whole decision back (fail closed);
5. cross-checks the append service's derived `role_used` against its own authorization; a
   divergence fails closed.

**Lock order (documented + tested):** target rows (`ReviewerRoleAssignment` / `ReviewerProfile`)
→ **chain head** (inside `append_decision`) → **bootstrap state**. A concurrent grant and
revoke serialise on the head, both commit, and leave a valid chain — verified by a
`TransactionTestCase` with genuine barrier contention.

**Self-elevation** is forbidden: a grant may not target the acting user
(`SELF_ELEVATION_FORBIDDEN`, audited). The policy says *who may grant*; this says they may
not grant to themselves.

**Idempotency:** grants are **non-idempotent** — a duplicate active grant is *rejected*
(fail closed), not silently returned. Revokes **are** idempotent — repeating an identical
revocation (same actor, same reason) appends no second event; a *conflicting* second
revocation (different actor/reason) fails closed. Nothing is ever deleted.

Every protected role event's signed payload carries: target user id, role, granted_at /
expires_at (or revoked_at), reason, prior assignment ids, and the canonical, explicitly
versioned `authz_snapshot/1.0` produced by
`authorization.build_authorization_snapshot`. DIP-1A-CORR-1 (`3046333`) replaced the older
reduced local snapshot after an end-to-end regression proved it failed full-chain
verification.

## Bootstrap closure — `BootstrapState` + the command

The pre-ledger bootstrap seeds the first reviewer authority before any authorized granter
exists. It must not remain a standing bypass, so closure is a **persisted fact**
(`BootstrapState` singleton, seeded open by migration 0005), not something re-derived from
the current role rows.

`manage.py bootstrap_reviewer_role` now permits seeding **only** when, checked under a row
lock on the singleton:

- `BOOTSTRAP_ENABLED = True` (deployment flag, off by default);
- a named **active Django superuser** operator (`--superuser`);
- the state is not already closed;
- no protected role-management DecisionEvent has ever been recorded;
- no active non-bootstrap reviewer authority already exists;
- target, role, expiry and reason are explicit.

The command records **no** DecisionEvent, so it does not itself close bootstrap. The state
closes **permanently** the first time a protected `role_services` call appends a
role-management event (`closed` goes False→True only, under `select_for_update`). Re-opening
is a deliberate **`--break-glass`** act, gated by `BOOTSTRAP_BREAK_GLASS_ENABLED` (off by
default), which increments `break_glass_count`, writes a **CRITICAL** `AuthorizationAudit`
record, grants nothing, and is never exposed through the web.

## Production role-seeding ceremony (summary)

1. Create the operator account as an active Django superuser (out of band).
2. Create the first reviewer's login account (active).
3. Set `BOOTSTRAP_ENABLED=true` for the ceremony only.
4. Run `manage.py bootstrap_reviewer_role --username <reviewer> --role BRAND_ADMIN
   --expires-days N --reason "<why>" --superuser <operator>`.
5. Unset `BOOTSTRAP_ENABLED`.
6. That first reviewer uses the protected `grant_reviewer_role` service to appoint others —
   which appends the first protected event and closes bootstrap permanently.

## NOT in 1A-5A (→ 1A-5B/1A-5C)

Attestation events, dual-control validation, historical role-validity verification, the
`verify_decision_chain` command, the full runbook set, and final reconciliation. No
approval, permission, retrieval, or automatic-use path is introduced.
