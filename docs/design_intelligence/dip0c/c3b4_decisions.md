# DIP-0C3b4 — decisions

## D1. Each scope axis gets its **own** taxonomy and its own comparison rules
There is no generic token relation. `EU` contains `FR` because of geography;
`PRIMARY` containing `PRIMARY_HORIZONTAL` is a claim about brand policy. One rule
cannot honestly serve both, so markets, products, lockups and variant roles each carry
their own registry, their own hierarchy, and their own `closed_world` flag.

## D2. DISJOINT is never inferred from the absence of an edge
Two registered tokens are disjoint **only** where the taxonomy says so — via
`mutually_exclusive_children`, `mutually_exclusive_roots` on a closed-world axis, or
an explicit `disjoint_peers` entry. A `PARENT` or `GENERAL` token with no recorded
relationship is `UNKNOWN`, because a category might contain the very thing it is being
compared against. `PACKAGING` vs `MASCARA` is UNKNOWN, not disjoint.

## D3. An unregistered token fails closed, and nothing is inferred from spelling
`LIPGLOSS` resolves to `LIP_GLOSS` because an **alias** says so. `LIP_GLOS` — a typo —
stays UNKNOWN. Any scope comparison touching an unresolved token returns
`SCOPE_UNKNOWN_OVERLAP` and goes to review. A review item costs a few minutes; a
silently-wrong "these don't collide" ships the wrong logo to a market.

## D4. Omission means ALL. Incompleteness means UNKNOWN. They are different facts
An axis carries a **mode** — `ALL` / `LIST` / `NONE` / `INCOMPLETE` / `INVALID` — and
the mode is recorded, not implied by an empty list. The schema defines omission as
`ALL` (which overlaps everything). Data that is *missing* never silently becomes
`ALL`; it becomes `UNKNOWN` and blocks.

## D5. Periods are half-open `[valid_from, valid_until)`
So a master ending exactly when its successor begins does **not** overlap it —
touching intervals are disjoint. Timestamps are normalised to UTC and the original
submitted value is preserved. A naive (timezone-less) timestamp is not a UTC instant
and is treated as malformed → `UNKNOWN`.

## D6. A proven DISJOINT on any one axis beats uncertainty everywhere else
If the markets provably cannot collide, the scopes cannot collide — even if the
product axis is unknown. That is the *only* thing that overrides an `UNKNOWN`.
Uncertainty on every other path fails closed.

## D7. Conflicts fail closed, and fail LOCALLY
Two masters fighting over France do **not** invalidate a master approved only for the
United States. A conflict blocks the affected scope — the conflicting scope, the
uncertain query scope, and proven-affected children — and leaves provably disjoint
scopes alone. Being maximally destructive is not the same as being safe; it just
teaches people to route around the system.

## D8. No winner is ever chosen by machine
Not by newest timestamp, not by filename, not by technical readiness. Two active
masters over one scope is `CANONICAL_CONFLICT`, both are unusable **as canonical for
that scope**, and it stays that way until a human picks one of the seven resolutions.

## D9. A resolution is ONE atomic compound file
A replacement is two facts — the incumbent retires, the successor activates. Writing
them as two files means that between the writes the ledger holds **two active masters
for one scope**, and a crash there makes that permanent. So the constituent events are
**embedded** in a single file, validated against the projected post-state, written to
a temp file on the same filesystem, fsynced, and installed with `os.replace()`. Either
the whole resolution is visible or none of it is. There is no torn state to detect,
because there is no interval in which one can exist.

## D10. Scope narrowing uses CONTAINMENT, not set difference
Narrowing `EU` → `FR` removes nothing from a set point of view — yet France is plainly
inside the EU. Set arithmetic would call that a *widening* and demand a full
reapproval for a genuine reduction. Only the taxonomy can tell the two apart, so
`narrowing_delta()` asks it: a requested token that **escapes** the previous scope is
a widening; a previous token no longer **covered** is a reduction. A change that
cannot be *proven* to reduce is refused — it might be widening in disguise.

## D11. Widening is a new approval, not a narrowing with a minus sign
Anything that adds applicability on any axis — including `LIST → ALL` — must pass the
complete dual-control canonical process. It may not be recorded as `SCOPE_REDUCED`.

## D12. Dual control survives the conflict path
Any resolution that **activates** a master (`SUPERSEDE_INCUMBENT`, replacement
activation) still requires both attestations from two distinct people. Enforced in
`conflict_resolution`, in `ledger.event()`, and again in `compound.validate()`. A
conflict is not an emergency that suspends the rules.

## D13. Every decision pins the taxonomy version it was made under
A taxonomy change must never silently reinterpret an old approval. If the pinned
version differs from the current one, the read model reports
`TAXONOMY_REVIEW_REQUIRED` and the original interpretation is preserved until a human
confirms the meaning has not moved.

## D14. The validator checks the committed ledger, not just the write path
`ledger_store.validate()` gained `overlapping_active_masters` and
`invalid_compound_events`. Checking only at write time would leave a hand-edited or
badly-merged ledger holding two active masters with nothing to notice.

## D15. Canonical decisions are never batch-approved
Queues A (candidates), B (conflicts) and C (replacements) carry
`batch_review_allowed = False`. Deciding which file *is* the brand is not a thing you
do fifty at a time.
