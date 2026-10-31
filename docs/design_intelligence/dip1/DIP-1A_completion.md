# DIP-1A — consolidated completion report

Identity, roles, and decision security for the Design Intelligence pipeline. Built by
composition on `django.contrib.auth.User` (no `AUTH_USER_MODEL` swap); the authoritative
actor is always `request.user.pk`.

## Slice map

| slice | delivered | key doc |
|---|---|---|
| 1A-1 | canonical serialization, content hashing, HMAC key registry, signing system check | `DIP-1A_security_model.md` |
| 1A-2 | ReviewerProfile / ReviewerRoleAssignment, point-in-time `active_roles`, migration 0001 | `DIP-1A_identity_model.md` |
| decouple | canonical policy moved into the app package; `tools/dip0c/authz.py` a thin re-export | `DIP-1A_policy_decoupling.md` |
| 1A-3 | `authorize_actor` service, enforcement, `AuthorizationAudit`, migration 0002 | `DIP-1A_authorization.md` |
| 1A-4 | signed append-only `DecisionEvent` chain + `DecisionChainHead`, append service, verifier, migration 0003 | `DIP-1A_decision_chain.md` |
| corrections | v2 envelope (signed supersession + algorithm), `role_used` derived internally, migration 0004 | `DIP-1A_security_correction_2025-07.md` |
| 1A-5A | protected role grant/revoke/enable/disable services, bootstrap closure, migration 0005 | `DIP-1A-5A_role_lifecycle.md` |
| 1A-5B | authenticated dual control + historical authorization | `DIP-1A-5B_dual_control.md` |
| 1A-5C | `verify_decision_chain` command, migration reconciliation, runbooks, this report | this file + `DIP-1A_runbooks.md` |
| CORR-1 | role lifecycle events use the canonical signed authorization snapshot; strict schema verification | `DIP-1A-CORR-1.md`; code commit `3046333` |

## Final production gate — each claim → its test

| gate criterion | evidence |
|---|---|
| authenticated Django users are authoritative actors | `test_authorization.py` (caller-supplied actor/role ignored); `AUTH_USER_MODEL == "auth.User"` asserted |
| reviewer roles are time-bound and immediately revocable | `test_models.py` (expiry/revocation fail-closed, point-in-time); `test_role_services.py::test_revoke_is_immediate…` |
| protected role lifecycle changes are signed and fully verifiable | `test_role_services.py` (atomic append/mutation) + `test_chain_verification.py::test_real_role_lifecycle_events_pass_complete_chain_verification` |
| bootstrap authority is closable; break-glass is audited | `test_role_services.py::test_bootstrap_closes…`, `…break_glass_reopens_with_critical_audit…` |
| production authorization uses one canonical policy | `test_authz_policy.py` + `tools/dip0c/tests/test_authz_decoupling.py` (wrapper re-exports the same objects) |
| callers cannot control actor / role / authorization data | `test_decision_chain.py::test_append_signature_has_no_role_used_param`; `test_attestation.py` reserved-field rejection |
| DecisionEvents are transactional, append-only, signed, chained | `test_decision_chain.py` (direct-write guards, fail-closed append, linkage) |
| supersession and signature-algorithm fields are signed | `test_security.py::test_golden_vector_v2_*`; `test_decision_chain.py` (repointed/algorithm tamper detected) |
| dual control uses distinct persisted authenticated users | `test_attestation.py::test_same_user_cannot_satisfy_both_halves`, `…two_distinct_authorized_users…` |
| historical authorization is verifiable | `test_attestation.py` (role validity at event time; later revocation doesn't invalidate); `test_chain_verification.py` |
| verification detects all supported tampering | `test_chain_verification.py` — one tamper per class (payload, HMAC, middle linkage, deleted row, head sig, unknown key, snapshot/envelope, role-history, assignment-row, policy-version, attestation lifecycle) |
| frozen milestone artifacts unchanged under normal tests | `tools/dip0c/tests/test_frozen_artifacts.py` + CI `git diff --exit-code` guard |
| migrations forward/rollback verified | `test_migration_0003.py`, `test_migration_final.py` (accounts zero→latest, PostgreSQL, CI) |
| fresh-database DecisionEvent count starts at zero | migrations seed only the genesis head; verified by `test_migration_final.py`; the configured local DB has no accounts ledger tables applied |
| no asset approval or operational permission is introduced by the DIP/accounts boundary | `test_role_services.py` / `test_attestation.py` boundary-local absent-surface tests |
| legacy authority is stated honestly | `DIP-1A-CORR-1.md` inventories repository-wide selection, gate, seed-status, logo-input, and production-output consumers |

## DIP-1A-CORR-1 — temporary reopen and closure

The role lifecycle services originally emitted a reduced, unversioned authorization
snapshot while the full-chain verifier required the complete 1A-5B snapshot. Before the
fix, a real four-action service-generated chain reproduced four fatal `INVALID` findings.
Code commit `3046333` removed the local vocabulary, made all four services use the existing
`authz_snapshot/1.0` builder, and made verification enforce the explicit schema and exact
field contract. No migration was required and no signed event was rewritten.

The configured PostgreSQL database was reachable during the correction but did not contain
the `accounts_decisionevent` table because accounts migrations were not applied there. It
therefore supplied no legacy event/action/snapshot distribution to preserve. Fresh database
migration tests continue to seed zero events. See `DIP-1A-CORR-1.md` for the producer matrix,
historical treatment, regression evidence, and read-only legacy authority inventory.

The DIP/accounts decision-security boundary introduces no asset approval, operational
permission, retrieval, or automatic-use capability. Legacy pipeline selection, approval,
seed-status, and automatic-input paths remain outside this boundary and must be contained by
the DIP-1B default-deny compatibility gateway.

## Verification classification (`verify_decision_chain`)

Read-only; exits non-zero only on FATAL.

- **FATAL:** `CHAIN_INVALID` (content hash / HMAC / linkage / head signature / sequence),
  `KEY_UNAVAILABLE` (recorded key absent — restore the retired key), `INVALID` (signed
  snapshot disagrees with its signed envelope), `ROLE_HISTORY_INVALID` (signed role did not
  authorize the action under the pinned policy).
- **WARNING (qualified, non-fatal):** `POLICY_REVIEW_REQUIRED`,
  `ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE` (unsigned assignment rows disagree with a signed
  snapshot — an out-of-chain mutation must not deny verification), `ATTESTATION_INEFFECTIVE`
  (expired/revoked/superseded — a normal lifecycle state),
  `IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY`.

Bounded mode is labelled diagnostic and never emits a bare `VALID` (a slice cannot establish
whole-chain linkage/head).

### Coverage honesty — real tamper vs defensive guards

`test_chain_verification.py` breaks one dimension per finding class. Two distinctions worth
stating plainly:

- **Reached by real tamper** (raw-SQL mutation of a genuinely produced chain):
  `CHAIN_INVALID` (payload / HMAC / middle-linkage / deleted row / head signature),
  `KEY_UNAVAILABLE` (unknown/absent key), `ATTESTATION_INEFFECTIVE` (a real lifecycle event),
  `ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE` (a real assignment-row mutation).
- **Real producer regression plus defensive guards:** DIP-1A-CORR-1 first reproduced
  `INVALID` using all four real role lifecycle services, then corrected their producer
  contract. Deliberately malformed, validly signed snapshots still exercise missing-field,
  schema-version, actor, role, action, and policy-drift guards without weakening production
  services or accepting partial snapshots.
- A `policy_version` edit on a real event is caught by the **HMAC first** (CHAIN_INVALID) —
  a downgrade cannot be smuggled past the MAC; the `POLICY_REVIEW_REQUIRED` warning path is
  exercised via a constructed signed event.

### One string-coupling to harden later

`KEY_UNAVAILABLE` vs `CHAIN_INVALID` is currently decided by matching the substring `"key"`
in `verify_event`'s free-text problem message. Both are fatal (the command fails either
way), but if that message is reworded, an unverifiable-key event would reclassify to
`CHAIN_INVALID` and the runbook's "restore the retired key" remediation would stop firing.
Maintenance/1A-5D should raise a typed `UnknownSigningKey` through `verify_event` instead of
matching text.

## Honestly-stated limitations (structural, not solved here)

- **Full database rollback** is undetectable in-database — needs an external anchor
  (transparency log / external timestamp / write-once storage). Future milestone.
- **HMAC ≠ personal signature** — it authenticates the application, not a human. Actor
  attribution rests on the authenticated Django session. Per-user asymmetric attestation is
  deferred.
- **Identity-state history** (`User.is_active`, `ReviewerProfile.reviewer_enabled`) is
  preserved only as the append-time snapshot observation, surfaced as
  `IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY`. Full account/profile history persistence is a
  DIP-1B or later extension.
- **`AuthorizationAudit`** is append-only through the app but not cryptographically
  tamper-evident against a DB superuser; the signed DecisionEvent chain is the stronger
  record.

## State boundary after correction

A fresh fully migrated database has a genesis head, **0 seeded DecisionEvents**, and an open
`BootstrapState`; DIP-1A provides the decision-security mechanism and activates no asset or
operational permission. The configured local database inspected during CORR-1 was not
migrated through the accounts ledger and therefore had no ledger table to verify.

Repository-wide legacy pipeline gates, active reference selection, seeded canonical/approved
statuses, automatic reference/logo inputs, and final-output authority remain present outside
the DIP/accounts boundary. They are characterized, not changed, by CORR-1 and are an explicit
input to the DIP-1B default-deny compatibility gateway.
