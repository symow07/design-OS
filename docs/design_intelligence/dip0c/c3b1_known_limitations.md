# DIP-0C3b1 — Known limitations

## 1. This is a model, not a workflow

C3b1 defines states, transitions, guards and defaults. It does **not** yet ingest
evidence, persist decisions, grant permissions, run expiry, approve canonical
masters or build queues. Those are C3b2–C3b4. Nothing in this slice is wired to
storage or to a UI.

## 2. No decisions are persisted

`human_confirmation` and `permissions` exist in the model and are blank/false. The
append-only decision ledger arrives in **C3b2**; until then a confirmation cannot
actually be recorded anywhere.

## 3. The certainty ranks are a judgement

Placing a business assertion at rank 2 (equal to an unconfirmed machine guess) is a
deliberate call. It is defensible and it is the safe direction — but it is a
modelling decision, not a measurement.

## 4. Authorisation is not modelled

The model says "human only". It does not yet say *which* human, nor check that a
reviewer is authorised to confirm ownership or approve a licence. Reviewer
authorisation belongs with the ledger in C3b2.

## 5. Machine revocation is available but not scheduled

`machine_revoke()` exists and is tested. Nothing calls it yet — expiry processing is
C3b3.

## 6. The model is per-file

It carries no notion of a brand, a product line or a market hierarchy, so
`approved_markets` / `approved_products` are flat lists. If scope needs to be
inherited (e.g. "approved for all EU markets"), that structure belongs in DIP-1.
