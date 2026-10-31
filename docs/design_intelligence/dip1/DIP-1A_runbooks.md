# DIP-1A — production security runbooks

Operating procedures for the reviewer identity, authorization, and signed decision chain.

## What the guarantees mean (read first)

- **Django authentication attributes an action to a user account.** The authoritative
  actor is `request.user.pk`; callers never supply actor, role, or authorization data.
- **The HMAC authenticates application-produced ledger records** — it is *tamper evidence*
  that a record was produced by an instance holding the signing key. It is **not a personal
  digital signature** and cannot prove a specific human acted.
- **Full database rollback remains undetectable without an external anchor.** Restoring an
  old database *and* its old, validly-signed chain head is internally consistent; detecting
  it needs transparency logs / external timestamping / write-once storage (a future
  milestone). No claim of full rollback protection.
- **Per-user cryptographic attestation (passkeys/hardware keys) is deferred** to a later
  security extension.

## 1. Production reviewer bootstrap ceremony

1. Create the operator account as an **active Django superuser** (out of band).
2. Create the first reviewer's login (active `auth.User`).
3. Provision the signing key in the secret store (§5) and set `DEBUG=False`.
4. Enable the ceremony: `BOOTSTRAP_ENABLED=true` (temporarily).
5. Run: `manage.py bootstrap_reviewer_role --username <reviewer> --role BRAND_ADMIN
   --expires-days <N> --reason "<why>" --superuser <operator>`.
6. Unset `BOOTSTRAP_ENABLED`.
7. That first reviewer uses the **protected** `grant_reviewer_role` service to appoint
   others — the first such event closes bootstrap permanently.

**`--role DESIGN_REVIEWER` is refused here** (DIP-1A-BOOTSTRAP-CORR-2): seeding a reviewer
directly recorded no protected role-management event, so bootstrap stayed open forever. This
ceremony seeds a role that can *then* use the protected service. For a single-operator local
development machine, where no two distinct humans exist, see §1a.

## 1a. Single-operator LOCAL DEVELOPMENT ceremony (not dual control)

`manage.py bootstrap_single_operator_reviewer --username <you> --expires-days <N≤30>
--reason "<why>"` — add `--dry-run` first to check readiness without prompting.

Requires `BOOTSTRAP_ENABLED` **and** `BOOTSTRAP_SINGLE_OPERATOR_ENABLED`, `DEBUG=True`,
`ENVIRONMENT=LOCAL_DEVELOPMENT`, a local database whose **name** is in
`LOCAL_DEVELOPMENT_DATABASES`, and an interactive password challenge against the account.
Grants a time-bounded `DESIGN_REVIEWER` only, and closes `BootstrapState` permanently in the
same transaction.

It is **explicitly not dual control**: the signed event carries `single_operator: true`,
`role_used` is the `BOOTSTRAP_OPERATOR` sentinel (not a real role), and the assignment's
`grant_source` is `BOOTSTRAP_SINGLE_OPERATOR`. It is a local development affordance and
system checks fail if its flag is set anywhere else. Full contract:
[DIP-1A-BOOTSTRAP-CORR-2](DIP-1A-BOOTSTRAP-CORR-2_single_operator_ceremony.md).

## 2. Protected role grant

Use `apps.accounts.role_services.grant_reviewer_role(actor=<authenticated user>,
target_user=…, role=…, expires_at=…, reason=…)`. The actor must hold BUSINESS_OWNER or
BRAND_ADMIN; a grant may not target the acting user (self-elevation is refused and audited);
a duplicate active grant is rejected. The role mutation, the signed DecisionEvent, and the
AuthorizationAudit commit atomically.

## 3. Role revocation

`revoke_reviewer_role(actor=…, assignment=…, reason=…)`. Immediate, append-only (the
assignment row is never deleted — `revoked_at/by/reason` are written), and a `ROLE_REVOKED`
event is appended. Repeating an identical revocation is idempotent; a conflicting one fails
closed.

## 4. Reviewer-profile disablement

`disable_reviewer_profile(actor=…, target_user=…, reason=…)` (BUSINESS_OWNER / BRAND_ADMIN /
SYSTEM_ADMIN). A disabled profile resolves to **no roles** immediately. `enable_reviewer_profile`
re-enables (appointing authority — SYSTEM_ADMIN forbidden).

## 5. DecisionEvent signing-key generation

Generate a **dedicated** ≥32-byte random secret — **never** `SECRET_KEY`. Store it only in
the production secret store. Configure:
`DECISION_EVENT_HMAC_KEYS='{"<key-id>":"<secret>"}'`, `DECISION_EVENT_ACTIVE_KEY_ID=<key-id>`.
Never commit it, never log it, never generate a replacement automatically at startup, never
fall back to `SECRET_KEY`. With `DEBUG=False` and no key, `manage.py check` fails by
design (`accounts.security.E001`).

## 6. HMAC key rotation

Add the new key to `DECISION_EVENT_HMAC_KEYS` and point `DECISION_EVENT_ACTIVE_KEY_ID` at
it. New events sign with the active key; the head is re-signed by the active key on the next
append. **Do not remove retired keys** — historical events record their own `signing_key_id`
and must keep verifying.

## 7. Retired-key retention

Retired keys stay in `DECISION_EVENT_HMAC_KEYS` **verification-only** for as long as any
event references them (effectively forever, given append-only history). An event whose
`signing_key_id` is not in the registry verifies as `KEY_UNAVAILABLE` (fatal) — remediation
is to **restore the retired key**, not to alter the event.

## 8. Chain verification

`manage.py verify_decision_chain` (read-only; writes/repairs nothing).
- `--format json|text`; `--from-seq N` / `--limit N` for a **bounded diagnostic** slice
  (which cannot establish whole-chain linkage/head — it never reports a bare `VALID`).
- Exits **non-zero** on any FATAL finding. Run it in monitoring and before trusting the
  chain.

## 9. Suspected chain tampering

Run `verify_decision_chain`. Classify the findings:
- **FATAL** `CHAIN_INVALID` (content hash / HMAC / linkage / head signature / sequence),
  `KEY_UNAVAILABLE`, `INVALID` (signed snapshot disagrees with its envelope),
  `ROLE_HISTORY_INVALID` (signed role did not authorize the action) → treat as an integrity
  incident; do **not** repair in place (there is no repair tool by design). Preserve the
  database, investigate provenance, restore from a trusted backup if warranted.
- **WARNING** `ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE` → the *unsigned* `ReviewerRoleAssignment`
  table disagrees with a signed snapshot: investigate a possible out-of-chain mutation of
  that table (this is **not** proof the event was unauthorized).

## 10. Authorization incident response

`AuthorizationAudit` records every allowed/denied attempt (structured reason codes; no
secrets/bodies). Filter by `reason_code`, `action`, `user`, `correlation_id`. It is
append-only through the app but **not** cryptographically tamper-proof against a DB
superuser (the signed DecisionEvent chain is the stronger record).

## 11. Bootstrap break-glass

Only if a closed environment genuinely needs re-seeding:
`BOOTSTRAP_BREAK_GLASS_ENABLED=true`, then `manage.py bootstrap_reviewer_role --break-glass
--superuser <operator>`. This re-opens bootstrap, increments `break_glass_count`, writes a
**CRITICAL** `AuthorizationAudit` record, and **grants nothing**. Never exposed via the web.

It **refuses** to reopen a closure anchored to a single-operator ceremony event
(`SINGLE_OPERATOR_BOOTSTRAP_REOPEN_REQUIRES_SEPARATE_REVIEW`), without incrementing
`break_glass_count` or clearing the anchor: that case has different consequences and needs
its own reviewed design.

## 12. Dual-control operation

Two authorized reviewers each record a complementary attestation (`record_attestation`) over
the **same** decision binding. `validate_dual_control(a, b)` (read-only) confirms two
distinct authenticated users, complementary categories, identical binding, chain validity,
and current effectiveness. **A valid pair activates nothing** — it is evidence, not an
approval.

## 13. Migration forward / rollback

Accounts migrations `0001`→`0005` are additive and reversible; `verify_decision_chain` and
the committed migration tests (`test_migration_0003`, `test_migration_final`, PostgreSQL,
in CI) confirm forward/rollback/re-apply preserve auth users and re-seed exactly one valid
genesis head with zero real events. Always back up PostgreSQL before a production migration
and inspect `sqlmigrate`.

## 14. Policy-version retention

Every protected event pins `policy_id`/`policy_version` in its signed snapshot. Keep the
canonical policy versioned; historical verification uses the recorded version. An unknown
recorded version yields `POLICY_REVIEW_REQUIRED` (a review warning) — never a silent
reinterpretation under the current policy.
