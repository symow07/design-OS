# DIP-0C3b2 — Completion Report

**Slice:** evidence records, business assertions, reviewer authorisation, the
append-only decision ledger, confirmation prerequisites, immutable audit history.
**Status:** complete, held for review before DIP-0C3b3.

**Scope guard:** no canonical-master approval, no permission granting, no expiry
processing, no review queues, no UI, no database. Permissions remain false
everywhere.

Reproduce: `python -m tools.dip0c.run_c3b2`.
DIP-0C3b1 commit: **`4e67309e5ded48a7720985a32e7a87434c24d17c`**.

---

## The transition-policy safeguard (applied first)

C3b1 let **certainty rank** authorise machine transitions. That was wrong, and it is
fixed. Uncertain states are **not a linear hierarchy**: `BBROSE_OWNED_UNCONFIRMED`
and `THIRD_PARTY_UNCONFIRMED` share a rank while being *materially different
hypotheses* — a machine moving between them is changing its mind about **who owns
the artwork**.

Now: **the explicit allowlist decides**; human-only states are refused to machines;
and **rank is an additional invariant that may only ever REJECT, never authorise.**

| | before | after |
|---|---|---|
| machine-legal ownership transitions | 37 | **18** |
| machine-legal licence transitions | 44 | **21** |

`MachineMayNotIncrease` now fires **zero** times across the matrix sweep — the
allowlist already excludes every increasing pair, so rank is pure defence-in-depth.
Lateral transitions are listed on purpose, flagged `lateral: true`, and must record
a **reason** and the **previous state**, which is never lost.

## The ledger ships EMPTY — and that is the point

`events/` **0** · `evidence/` **0** · `assertions/` **0**.

No ownership is confirmed, no licence approved, nothing granted. **A fabricated
approval would be worse than no approval**, because it would look like a decision
someone actually made. The synthetic records live in `examples_TEST_ONLY/`, each
flagged `TEST_ONLY: true`, and the read model never loads them.

## Schemas implemented

**13 event types** — `ASSERTION_SUBMITTED` · `ASSERTION_WITHDRAWN` ·
`EVIDENCE_SUBMITTED` · `EVIDENCE_ACCEPTED` · `EVIDENCE_REJECTED` ·
`OWNERSHIP_CONFIRMED` · `THIRD_PARTY_CONFIRMED` · `LICENSE_APPROVED` ·
`LIMITED_USE_APPROVED` · `OWNERSHIP_REVOKED` · `LICENSE_REVOKED` ·
`DECISION_SUPERSEDED` · `RE_REVIEW_REQUIRED`.

**15 evidence types**, **6 statuses** (`SUBMITTED`, `REVIEWED_ACCEPTED`,
`REVIEWED_REJECTED`, `EXPIRED`, `SUPERSEDED`, `QUARANTINED`).

IDs are derived from the record's substance (deterministic, collision-safe). Content
hashes exclude `content_hash`, `recorded_at` and `repository_commit`, so records
re-hash deterministically and any edit to their substance is caught.

## Authorised roles and actions

**Git authorship is provenance, not authorisation.** Every event is validated
against the actor's role.

| Action | Permitted roles |
|---|---|
| `submit_assertion` / `withdraw_assertion` | BUSINESS_OWNER, BRAND_ADMIN |
| `submit_evidence` | BUSINESS_OWNER, BRAND_ADMIN, LEGAL_REVIEWER, DESIGN_REVIEWER |
| `review_evidence` | LEGAL_REVIEWER, BRAND_ADMIN, DESIGN_REVIEWER |
| `confirm_ownership` / `confirm_third_party` | LEGAL_REVIEWER, BRAND_ADMIN |
| **`approve_license` / `approve_limited_use`** | **LEGAL_REVIEWER only** |
| `revoke_decision` | LEGAL_REVIEWER, BRAND_ADMIN, SYSTEM_ADMIN |

**No role may do everything.** A `SYSTEM_ADMIN` may revoke and quarantine but may
**not** confirm ownership or approve a licence — administrative power is not legal
authority. A `DESIGN_REVIEWER` may review evidence about the artwork but may not
decide who owns it. `OBSERVER` appears in no policy entry: read-only by
construction.

## Confirmation prerequisites — all six

An authorized reviewer · at least one **REVIEWED_ACCEPTED** evidence record · an
explicit reason · evidence references · a legal transition per the matrix · and no
unresolved contradiction.

## The LOGO6.ai case, exercised

A `LEGAL_REVIEWER` attempts to confirm BBROSE ownership of `LOGO6.ai` on the
strength of the business's assertion. **REFUSED**, for two independent reasons:

1. *"no REVIEWED_ACCEPTED evidence: a business assertion is a BELIEF, not evidence,
   and can never on its own support a confirmation"*;
2. *"a contradiction is present and has NOT been acknowledged"* — the artwork's own
   live text reads **"global logistics services"**.

A reviewer *may* still confirm despite the contradiction — but only by acknowledging
it explicitly, on the record, with a reason. That path is tested too.

By contrast, third-party confirmation of `JOJIA LOGO.ai` (accepted evidence: the
wordmark reads *"Jojiia"*; authorized legal reviewer; legal transition) is
**allowed** — the happy path exists.

## Append-only enforcement — 12 checks

modified records · deleted records · duplicate ids · broken supersedes · missing
evidence refs · missing assertion refs · invalid actor roles · unauthorized actions
· illegal state transitions · invalid timestamps · hash mismatches · index
divergence.

`index.json` is **generated** and doubles as a **deletion tripwire** — it remembers
what existed and what it hashed to. It is explicitly *not* the source of truth.

Verified by test: editing a file on disk is detected · deleting one is detected · an
existing record cannot be overwritten · a correction **appends** and the original
survives · a corrective event **must** reference what it supersedes · a withdrawn
assertion is **not deleted**.

## Machine/human separation

A ledger event **never** modifies machine inference — tested. The effective state is
a **derived read model** (machine inference + assertions + accepted evidence +
decisions + revocations); it is a projection, never written back, and the immutable
files remain the source of truth.

**Permissions stay false even after a confirmation** — granting is C3b3.

## Tests / lint / integrity

- `pytest tools/dip0c/tests/test_c3b2.py` — **28 passed**;
  `test_c3b1.py` — **42 passed** (grew with the safeguard).
- `ruff check tools/dip0c` — clean.
- **Materials unchanged**; no database, no UI, no migrations (asserted by test).

## Findings requiring adjustment before C3b3

1. **Identity is unverified.** The tool checks that the *role* may act; it does not
   verify that the `actor_id` really is that person. In practice the PR reviewer is
   the check. Identity binding is DIP-1.
2. **The deletion tripwire depends on the index being committed.** A deletion plus an
   index regeneration in one commit would evade the *tool* — git history still
   catches it. Tamper-evidence is git **plus** the index, not the index alone.
3. **Content hashes are not signatures.** They make careless edits visible; an actor
   who edits and re-hashes is caught by git, not by the hash.
4. **Expiry is modelled but not scheduled.** `review_expiry` is carried on decision
   events and `machine_revoke()` exists — nothing runs them yet. That is C3b3, and
   it is safe precisely because revocation only ever *reduces*.

**HOLD** for review before starting DIP-0C3b3.
