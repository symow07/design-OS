# DIP-0C3b2 — Decisions

## 1. The real ledger ships EMPTY

No ownership confirmed, no licence approved, nothing granted. A fabricated approval
would be *worse than no approval*, because it would look like a decision someone
made. The synthetic records live in `examples_TEST_ONLY/`, every one flagged
`TEST_ONLY: true`, and the read model never loads them.

## 2. Git authorship is provenance, NOT authorisation

Knowing who committed a decision does not establish they were entitled to make it.
Every event is validated against the actor's **role** and the requested **action**.

## 3. No role may do everything

- `SYSTEM_ADMIN` may revoke and quarantine but may **not** confirm ownership or
  approve a licence — *administrative power is not legal authority*.
- `DESIGN_REVIEWER` may review evidence about the artwork but may not decide who
  owns it.
- `APPROVE_LICENSE` is `LEGAL_REVIEWER` **only**.
- `OBSERVER` appears in no policy entry: read-only by construction.

## 4. Submission is not acceptance; acceptance is not approval

Evidence enters as `SUBMITTED`. A reviewer must accept it. **Evidence status never
automatically changes an ownership or licence state** — only a decision event does,
and only a human makes one.

## 5. A confirmation needs six things

An authorized reviewer · at least one REVIEWED_ACCEPTED evidence record · an
explicit reason · evidence references · a legal transition (per the matrix) · and no
unresolved contradiction.

## 6. Contradiction must be acknowledged out loud

A reviewer *may* confirm despite conflicting evidence — but only by saying so
explicitly, on the record, with a reason. **`LOGO6.ai` is the case this exists
for**: the business believes it owns the logo, and the artwork's own live text reads
*"global logistics services"*. The synthetic attempt to confirm it is **refused**,
for two independent reasons.

## 7. Corrections append; history stays complete

No record is edited in place. A correction is a new event that references what it
supersedes. A withdrawn assertion is *not deleted* — the belief and its withdrawal
both remain visible.

## 8. Sensitive evidence is referenced, never committed

Contracts, invoices and emails stay out of the repository. The evidence record
carries a path/URI and a file hash.
