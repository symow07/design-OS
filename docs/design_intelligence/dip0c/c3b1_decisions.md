# DIP-0C3b1 — Decisions

## 1. The invariant is one rule, enforced in one place

*Machine code may only ever reduce certainty or permission.* Rather than repeating
"don't approve this" at every call site, it is enforced centrally by
`validate_transition()` and `machine_permission_update()`. Every other guard in the
slice is a consequence of it.

## 2. "Reduce" is made checkable by a certainty rank

A slogan cannot be tested. Each state has a rank, and a machine transition may only
move to a rank `<=` the current one. That turns the invariant into a property the
validator enumerates across **every** (from, to) pair, rather than a promise.

## 3. A belief ranks no higher than a guess

`BUSINESS_ASSERTED_BBROSE` has rank **2** — the same as
`BBROSE_OWNED_UNCONFIRMED`, and far below any confirmed state. The business
believing something does not make it more likely to be true than the evidence says.
`LOGO6.ai` is the live example: the business may well believe it owns that logo, and
the file's own live text reads *"global logistics services"*.

## 4. A business assertion survives contradiction

When the machine disputes ownership, the assertion is **not** erased. Both remain
visible, so the reviewer sees the belief *and* the evidence against it. It may only
be withdrawn by a human, and the withdrawal is recorded rather than deleted.

## 5. Ownership and licence are separate axes, and neither implies a permission

Confirming ownership does not approve a licence. Approving a licence does not prove
ownership. And **neither grants a single permission.** Permission is a fourth,
independent layer that only a human writes, flag by flag.

## 6. The four layers have disjoint key sets

Not by convention — by construction, and verified. A layer physically cannot write
into another, so "human review does not mutate machine inference" is a structural
property rather than a discipline someone has to remember.

## 7. Automatic expiry is safe *because* of the invariant

Expiry revokes a permission (`true -> false`) and downgrades a licence to
`EXPIRED_OR_REVIEW_REQUIRED` (rank 0). Both are reductions, so a machine may perform
them. Restoring them is a human decision. That is why an expired approval can be
revoked automatically without ever risking an automatic grant.
