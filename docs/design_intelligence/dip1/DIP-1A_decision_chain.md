# DIP-1A-4 — the signed decision-event chain

A tamper-evident, append-only record of protected decisions. Two models, one append
service, one read-only verifier. Builds directly on the frozen 1A-1 primitives (canonical
serializer, SHA-256 content hash, HMAC key registry) — their golden vectors still pass, so
event 1 links to `previous_event_hash: null` exactly as fixed there.

## Models

**`DecisionEvent`** — one signed, **immutable** link. Signed content is the frozen 1A-1
12-field envelope (`SIGNED_FIELDS`): schema_version, event_id, sequence_number, actor_id,
role_used, action, subject_type, subject_id, payload, previous_event_hash, created_at,
signing_key_id. Stored also: content_hash, hmac_signature, signature_algorithm,
supersedes_event, created_at.

- `created_at` is generated **once** by the append service and stored unchanged (never
  `auto_now_add`) — the persisted timestamp is exactly the signed one.
- The numeric PK is **not** in signed content.
- `supersedes_event` and `signature_algorithm` are **outside** the frozen 12 and are
  therefore **unsigned metadata in 1A-4** — honestly flagged. A superseding *decision*
  (1A-5) will carry its reference inside the signed payload; the verifier **pins**
  HMAC-SHA-256 rather than trusting the `signature_algorithm` column (no downgrade path).
- Unique `event_id`, unique `sequence_number`; indexes on actor, action, (subject_type,
  subject_id), created_at, supersedes_event; CHECKs that event_id/content_hash/
  hmac_signature/signing_key_id are non-empty.

**`DecisionChainHead`** — the signed terminal state, a **singleton** (pk=1, CHECK id=1):
chain_id, terminal_sequence_number, terminal_event_hash, event_count, schema_version,
signing_key_id, head_signature. The signed head payload is the 1A-1 `HEAD_SIGNED_FIELDS`.

## Write guards (different for the two models)

Both are writable **only** through the append service, which holds the one in-process
capability token (identity check, not a value an attacker can forge from JSON):

- **DecisionEvent** — insert-only: `objects.create()`, `save()` without the token,
  `save()` on a loaded row, `update()`, `delete()`, `bulk_create()`, `bulk_update()` all
  raise `ChainWriteViolation`. Corrections append a superseding event; nothing is mutated.
- **DecisionChainHead** — the service *advances* it, so `save()` (with token) is allowed,
  but `create()`/`delete()` are blocked so the singleton can be neither duplicated nor
  removed.
- Admin registers both **read-only**.

## Genesis

Migration `0003` seeds one **unsigned** genesis head (seq 0 / count 0 / terminal hash
NULL / no signature) via `RunPython` — migrations must not depend on production signing
secrets. The unsigned state is permitted **only** while seq=0, count=0, and no event
exists. The first append validates that exact genesis and replaces it with a signed
non-empty head in the same transaction. Any non-empty chain therefore has a valid signed
head.

## Append service — `append_decision(...)`

One transaction, serialised on the head:

1. `transaction.atomic()`.
2. `select_for_update()` the singleton head; **fail closed if missing** — never
   create-on-append (that is the fork window).
3. Validate the current chain (genesis pristine, or head signature + terminal event
   content-hash/HMAC + row count all agree).
4. Resolve `event_id` (server-generated uuid4 hex if absent).
5. Idempotency on `event_id`, comparing **business fields** (actor, role_used, action,
   subject, payload) — sequence/timestamp/linkage do not exist yet, so `content_hash`
   cannot be compared here. Same id + same content → return existing; different → conflict.
6. Validate inputs (known action/role, bounded subject, canonical-serialisable payload, no
   reserved payload keys, supersedes persisted).
7. Generate one UTC timestamp; **re-run `authorize_actor` at that instant** as the
   authoritative check and cross-check the bound frozen `AuthorizationResult` (same actor,
   role_used, action, subject) — catches a role revoked between the 1A-3 decision and the
   append. A raw dict is refused.
8. Allocate `sequence = head.terminal + 1`, `previous_event_hash = head.terminal_event_hash`
   (NULL at genesis → event 1 null).
9. Sign the envelope with the **active** key → content_hash, hmac_signature.
10. Insert the event through the token path.
11. Build + sign the advanced head; update the locked head.

Any failure → nothing written, head unmoved, transaction rolled back.

## Authorization-result binding

The service accepts the **frozen** `AuthorizationResult` from 1A-3 (not an arbitrary
dict) and verifies allowed + actor + role_used + action + subject match, then re-derives
authorization at the append timestamp. "Sufficiently recent" is satisfied by construction:
the authoritative check *is* the append-time re-derivation.

## Key rotation

New events sign with the active key only; each event records its own `signing_key_id`.
Retired keys stay in the registry **verification-only**, so history keeps verifying after a
rotation; an unknown/absent key fails closed. The head is re-signed by the active key on
the next append. Verified end-to-end: event 1 under `k1`, event 2 under `k2` after
rotation, both verify.

## Verifier — `verify_chain()` (read-only, never repairs)

Walks the whole chain and reports every problem: sequence monotonicity + no gaps,
previous-hash linkage, recomputed content hash, HMAC (pinned HMAC-SHA-256, via each
event's recorded key id), actor/role/action validity, supersedes sanity, and head
(signature, event_count, terminal sequence/hash). Returns a frozen result; writes nothing.

## Concurrency

Verified with a `TransactionTestCase`, two threads on separate PostgreSQL connections, a
barrier forcing genuine contention — including the **first** append on the empty chain.
They serialise on the head row: distinct monotonic sequences, one head, intact linkage,
valid signed head. Concurrent identical retries (same `event_id`) produce exactly one row.

## Limitations (not hidden)

- **Rollback:** restoring both an older database and its older, validly-signed head yields
  an internally consistent past that no in-database check can distinguish. Detecting that
  needs an external anchor (transparency log, external timestamp, write-once storage) —
  documented, not solved here. No claim of full rollback protection or cryptographic
  immutability.
- **Not personal non-repudiation:** the HMAC proves application-key possession, not that a
  specific human signed. Per-user asymmetric signing is a later, separate milestone.
- `supersedes_event` unsigned in 1A-4 (above).

## Migration safety (verified)

`0003_decisionevent_decisionchainhead` creates only the two new tables (+ constraints,
indexes, additive FKs to `auth_user` and self); alters no existing table. Forward
alongside all migrations, reverse to 0002 (users preserved), re-apply — all clean. After
migration: genesis head valid, `verify_chain().ok`, **zero** real DecisionEvent rows.

## NOT in 1A-4 (→ 1A-5+)

Protected ownership/license/canonical/palette/permission endpoints, real approval actions,
role-grant/revoke production services, dual-control activation, review UI, ingestion,
retrieval, automatic use, per-user asymmetric signing.
