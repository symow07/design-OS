# DIP-1A security correction (pre-1A-5)

A follow-up record — **the earlier milestone docs are not rewritten.** Two mandatory
corrections to the 1A-4 signed decision chain, applied before any real superseding
decisions exist, plus a committed migration-executor test.

## Correction 1 — supersession and algorithm are now SIGNED (schema `decision_event/2.0`)

In 1A-4, `supersedes_event` and `signature_algorithm` were **outside** the frozen 12-field
v1 envelope, i.e. unsigned metadata. That is now fixed with a new signed schema.

- `canonical.SIGNED_FIELDS_V2` (14 fields) = the v1 twelve **plus** `supersedes_event_id`
  and `signature_algorithm`. `canonical.signed_payload_v2(...)` builds it.
- **v1.0 is untouched and frozen** — the 1A-1 golden vectors still pass byte-for-byte, and
  `signed_payload` (v1) remains only for those fixtures. No real event is v1.
- `DecisionEvent` now defaults to `decision_event/2.0`; the append service signs the v2
  envelope. `supersedes_event_id` is the referenced event's **stable `event_id`** (never a
  database pk), or `null` for a normal event.
- **Append-time supersession validation:** the reference must be persisted, **precede** the
  new event, and concern the **same subject AND the same action** (decision domain) —
  `SupersessionError` otherwise. (Action-compatibility is enforced, not deferred: a
  correction supersedes the same *kind* of decision.)
- **Verifier rejects:** a repointed supersession (the recomputed content hash no longer
  matches — the referenced `event_id` is signed), a missing referenced event, a forward
  reference, an incompatible-subject or incompatible-action reference, and any
  `signature_algorithm` other than the pinned `HMAC-SHA-256` (the verifier pins the
  algorithm; it never selects it from the column — no downgrade path).

**v2 is byte-pinned by a golden vector** (`test_golden_vector_v2_*`), the same anti-drift
guarantee v1 has — because every real event is now v2, and a v2 serializer drift would
otherwise pass unnoticed (sign and verify move together) while silently breaking every
previously-signed v2 event. There are zero real events, so no data migration is required.

## Correction 2 — the caller may not pass `role_used`

The append service now derives `role_used` **internally** and the public signature no
longer accepts it (nor a pre-built authorization result):

```
append_decision(*, user, action, payload, subject=None, event_id=None, supersedes=None)
```

Inside, it calls the canonical 1A-3 `authorize_actor` at the append timestamp, resolves
active roles from persisted assignments, selects `role_used` deterministically
(least-privilege-by-action-breadth), and writes that derived role into the signed payload.
The caller controls **none** of: actor id (from `request.user`), active roles, authorizing
roles, selected role, or the authorization result. A denied actor appends nothing
(`AuthorizationDenied`). `role_used` is a reserved (signed-envelope) key, so it cannot even
ride inside `payload`.

Tests prove: the signature has no `role_used`/`authorization` parameter; an actor holding
both a specialist and a broad role has the specialist derived (caller cannot force the
broader one); the stored role equals the canonical decision; a payload-supplied role is
refused; and an authorization mismatch/denial appends nothing.

## Committed migration-executor test

`apps/accounts/test_migration_0003.py` (a `TransactionTestCase`, runs in CI) drives
`MigrationExecutor` 0002⇄0003: rollback drops only the two decision-chain tables while auth
users / reviewer profiles / role assignments / authorization audits survive; the forward
re-application re-seeds a valid genesis head with zero real events and `verify_chain().ok`.

## Unchanged limitations (still recorded, not solved here)

- **Full database rollback** (restoring an older DB *and* its older valid signed head) is
  undetectable in-database; needs an external anchor. A future hardening milestone is named
  in the 1A-5 documentation set (external signed checkpoints, independent timestamping,
  transparency log, append-only external storage, deployment anchors). No claim of full
  rollback protection.
- **HMAC authenticates the application, not the individual.** Actor attribution rests on
  the authenticated Django session; per-user asymmetric attestation remains future work.
