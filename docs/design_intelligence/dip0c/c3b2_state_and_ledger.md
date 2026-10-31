# DIP-0C3b2 — State and ledger

## The transition matrix is authoritative; rank only rejects

C3b1 authorised machine transitions by certainty rank. That was wrong, and it is
fixed here.

Uncertain states are **not a linear hierarchy**. `BBROSE_OWNED_UNCONFIRMED` and
`THIRD_PARTY_UNCONFIRMED` share a rank while being *materially different
hypotheses* — a machine moving between them is changing its mind about **who owns
the artwork**, which is exactly the kind of change that must be deliberate.

So:

1. **The explicit allowlist decides.** A transition is legal only if it is listed.
   Nothing becomes legal merely because its rank is equal or lower.
2. **Human-only states** are refused to machine actors.
3. **Rank is an additional invariant that may only REJECT.** It never authorises.

Effect: machine-legal transitions dropped from 37 → **18** (ownership) and
44 → **21** (licence). `MachineMayNotIncrease` now fires **zero** times in the
matrix sweep — the allowlist already excludes every increasing pair, so rank is
pure defence-in-depth.

**Lateral transitions** (equal rank = a different hypothesis) are listed on purpose,
flagged `lateral: true`, and must record a **reason** and the **previous state**.
The previous state is never lost.

## The ledger

Append-only, one immutable JSON file per record, under
`docs/design_intelligence/dip0c/decisions/`.

- **The files are the source of truth.** `index.json` is generated — and doubles as
  a **deletion tripwire**: it remembers what existed and what it hashed to.
- **Content hashes** exclude `content_hash`, `recorded_at` and `repository_commit`,
  so a record re-hashes deterministically and any edit to its substance is caught.
- **IDs are derived from the record's substance** — deterministic and collision-safe.
- **Corrections append.** `DECISION_SUPERSEDED`, `OWNERSHIP_REVOKED`,
  `LICENSE_REVOKED`, `EVIDENCE_REJECTED`, `ASSERTION_WITHDRAWN`,
  `RE_REVIEW_REQUIRED` — each references the event it supersedes. Nothing that was
  ever true disappears.

## The read model is derived

The effective state is *computed* from immutable machine inference + assertions +
accepted evidence + append-only decisions + revocations. It is a projection. The
ledger remains the source of truth, and the read model is never written back.

A ledger event **never** modifies machine inference — tested.
