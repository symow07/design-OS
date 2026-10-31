# DIP-1A — security model (slice 1A-1)

## What the HMAC proves — and what it does not

**It proves:** a decision-event record was produced by an application instance holding an
authorized signing key. A row edited directly in the database — by a DB superuser, by raw
SQL, by a partially restored backup — will **not** verify.

**It does not prove:** that a particular human held a private key. It cannot support
non-repudiation. **Any application instance with the key can produce any event.**

Attribution of an action to a human rests on the **authenticated Django session** and the
**authorization policy** — not on this MAC. That distinction is written down because it is
exactly the kind of thing that gets quietly upgraded in a summary, until someone believes
the database can prove *who* approved a licence. **It cannot.**

Per-user asymmetric signing (WebAuthn / passkeys / hardware keys) is a separate planned
milestone: **DIP-1 Security Extension — Human Cryptographic Attestation.**

## The claim we are allowed to make

> **The database is not immutable.** A sufficiently privileged actor can write anything.
> **Unauthorized mutation is *detectable* while the signing key remains uncompromised.**

We never claim cryptographic immutability, and we never claim full rollback protection.

## Canonical serialization — `apps/accounts/security/canonical.py`

The bytes that get signed must be reproducible, byte-for-byte, years later, by code that
has been refactored in between. If the serializer can drift, the signature proves nothing:
a verifier would report a mismatch for every historical event, and the chain would be
worthless exactly when it mattered.

| rule | why |
|---|---|
| UTF-8, `ensure_ascii=False` | the bytes are the bytes, not `\uXXXX` escapes |
| sorted object keys | key order is never incidental |
| separators `(",", ":")` | no whitespace drift |
| **NaN / Infinity → raise** | not valid JSON; `NaN != NaN` makes verification non-deterministic *by definition* |
| **naive datetime → raise** | it names no instant |
| datetimes → **UTC ISO-8601** | one representation of one moment |
| `Decimal` → **string** | `Decimal → float` loses precision; `1.10` and `1.1` are different values |
| **list order preserved** | a list of attesters is not the same decision in a different order |
| **unsupported type → raise** | a type silently coerced to a string would change the bytes and break every signature after it |
| non-string key → raise | no deterministic ordering |

**`str(dict)` and unspecified `json.dumps` are never signed.**

### Signed fields (12)

`schema_version` · `event_id` · `sequence_number` · `actor_id` · `role_used` · `action` ·
`subject_type` · `subject_id` · `payload` · `previous_event_hash` · `created_at` ·
`signing_key_id`

### Excluded — and why

| field | reason |
|---|---|
| `id` | database-generated primary key — not known at signing time |
| `content_hash` | derived **from** the signed bytes; signing it would be circular |
| `hmac_signature` | derived from the signed bytes |
| `created_at_db` | an `auto_now_add` value would **replace** the signed timestamp |
| `updated_at` | mutable by definition; a signed event is never updated |

**`created_at` is generated once by the append service and stored unchanged.** It is never
`auto_now_add`: the database would assign that *after* signing, the signed timestamp would
then differ from the persisted one, and the chain would fail verification on every row for
a reason nobody could find.

## Golden vectors

The tests pin the exact bytes, SHA-256 and HMAC of a known payload. **If a future refactor
changes what the serializer emits, those tests fail — which is the entire point.** A
serializer that can change without anyone noticing can silently reinterpret history.

```
{"action":"confirm_ownership","actor_id":7,"created_at":"2026-07-14T12:00:00+00:00",
 "event_id":"evt-0001","payload":{"note":"ok"},"previous_event_hash":null,
 "role_used":"LEGAL_REVIEWER","schema_version":"decision_event/1.0",
 "sequence_number":1,"signing_key_id":"k1","subject_id":"face-abc",
 "subject_type":"FontFace"}
```

## Key management — `DECISION_EVENT_HMAC_KEYS`

**A dedicated secret. Never `SECRET_KEY`** — reusing it would mean anything able to forge a
session could also forge a decision event, and the two must fail independently. A test
walks the AST of `signing.py` and asserts it never reads `settings.SECRET_KEY`.

```
DECISION_EVENT_HMAC_KEYS='{"2026-07":"<32+ byte secret>","2026-01":"<old secret>"}'
DECISION_EVENT_ACTIVE_KEY_ID='2026-07'
```

- supplied by **environment / secret store**; **never** in the database, **never** committed
- **only the active key signs**; every other key is **verification-only**, so a rotation
  never invalidates history
- **unknown key id → fails closed** (`UnknownSigningKey`) — never "verify anyway"
- **duplicate key id → fails startup validation** (one would silently overwrite the other,
  and events signed with the loser could never verify)
- **active key with no material → fails closed**
- keys shorter than **32 bytes** are refused: a short MAC key is a decoration
- verification uses `hmac.compare_digest` — a timing oracle on a MAC comparison is a real
  attack
- algorithm: **HMAC-SHA-256**

## System check

`accounts.security` — **`E001` (error) when `DEBUG=False`**, **`W001` (warning) in
development**. Same condition, different severity, **different id**: an `E`-prefixed id on
a `Warning` object reads as an error in every log aggregator.

**A production instance that cannot sign must not pretend it can.** An unverifiable
decision event is worse than a missing one, because it looks like evidence.

> ⚠️ **Deployment note:** with `DEBUG=False` and no key configured, `manage.py check`
> **exits non-zero**. That is intended — but it means **the key must be set in the
> production secret store before the next deploy**, or the deploy will fail the check. No
> decision events exist yet, so there is no data risk; it is purely a configuration
> prerequisite.

## Chain head (used by 1A-4)

`signed_head_payload()` signs `chain_id`, `terminal_sequence_number`,
`terminal_event_hash`, `event_count`, `signing_key_id`.

Signing events alone leaves a gap: **delete the last N rows and every remaining link still
verifies.** Signing the head's terminal sequence, terminal hash and event count makes that
truncation detectable, because the head then disagrees with the table.

### The limitation we do not hide

**A full rollback is not detectable from the database alone.** An attacker who restores
*both* the table and an older, genuinely-signed head from a backup produces a state that is
internally consistent and indistinguishable from the past.

Closing that needs an **external anchor**: transparency logs, externally anchored
checkpoints, signed release manifests, write-once storage, external timestamping. Recorded
as a known limitation, deliberately not solved here.

## Scope of 1A-1

**No models. No migrations. No endpoints. No events.** Pure functions only:
canonical serialization · SHA-256 content hashing · HMAC signing · key registry · system
check. A test asserts `accounts/models.py` is empty, that no migration exists, and that
`AUTH_USER_MODEL == "auth.User"`.
