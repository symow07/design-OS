# The decision ledger

**This ledger is EMPTY, and that is correct.**

No ownership has been confirmed. No licence has been approved. Nothing is granted.
Fabricating a decision that no authorized human actually made would be worse than
having none at all, so `events/`, `evidence/` and `assertions/` contain no real
records.

## What is here

| Path | What it is |
|---|---|
| `events/` | **empty** — real human decisions go here, one immutable file each |
| `evidence/` | **empty** — real evidence records |
| `assertions/` | **empty** — real business assertions |
| `index.json` | **GENERATED.** A convenience, and a deletion tripwire. **Not the source of truth.** |
| `schemas/` | the record schemas and the authorisation policy |
| `templates/` | blank templates to copy |
| `examples_TEST_ONLY/` | **synthetic**. Every record is flagged `TEST_ONLY: true` and confers nothing. |

## The rules

- **The record files are the source of truth.** `index.json` is generated from them.
- **A record is never edited or deleted.** A correction is a *new superseding event*.
  History stays complete.
- **Git is the audit trail** — authorship, timestamps, diffs and review come free.
- **Git authorship is provenance, not authorisation.** Every event is validated
  against the actor's *role* and the action requested.
- **Evidence is not approval.** A confirmation needs reviewed-and-accepted evidence,
  an authorized reviewer, an explicit reason, a legal transition, and — where
  evidence conflicts — an explicit acknowledgement of the contradiction.
- **A business assertion is a belief.** It confirms nothing and grants nothing, and
  it survives being contradicted.
- **Sensitive evidence is referenced by path/hash — never committed.** Contracts,
  invoices and emails do not belong in this repository.

## Adding a real decision

1. Copy the relevant template from `templates/`.
2. Fill it in. The `content_hash` and the id are generated from the record's
   substance.
3. Place it in `events/`, `evidence/` or `assertions/`.
4. Run `python -m tools.dip0c.run_c3b2` to validate and regenerate the index.
5. Commit. Git records who added it and when.

The validator will refuse an unauthorized actor, an illegal transition, a broken
reference, a duplicate id, an edited record or a deleted one.
