# DIP-0C3b2 — Known limitations

## 1. Nothing is granted yet

Permissions remain false everywhere. Granting, canonical-master approval and expiry
processing are **C3b3**; review queues are **C3b4**. A confirmation recorded today
still activates nothing.

## 2. Roles are static and identity is unverified

The authorisation policy is configuration-backed. The tool checks that the *role* on
an event may perform the action — it does **not** verify that the `actor_id` really
is that person. Identity binding (and database-backed roles) is DIP-1. In practice
the reviewer of the pull request is the check.

## 3. The tripwire depends on the index being committed

Deletion is detected by comparing the working tree against `index.json`. If a
deletion and an index regeneration are committed together, the *tool* will not see
it — **git history will**. The ledger's tamper-evidence is git plus the index, not
the index alone.

## 4. Timestamps are asserted, not attested

`occurred_at` is supplied by the submitter. Nothing cryptographically attests when a
decision was really made; `recorded_at` and the git commit date bound it.

## 5. The read model is recomputed, not cached

Fine at this scale, and it keeps the ledger unambiguously the source of truth. If it
ever needs to be fast, the projection belongs in DIP-1 — never the ledger.

## 6. No cryptographic signatures

Content hashes detect *accidental or careless* modification and make edits visible.
They are not signatures: an actor who edits a record and regenerates its hash would
be caught by git history, not by the hash.
