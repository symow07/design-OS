# DIP-0C5 — known limitations

## L1. Authenticated identity — the production-readiness blocker
Four dual-control gates compare **asserted** actor IDs. "Two people" means "two names".
**No real dual-control approval may become operational until this is fixed.** Everything
else in this list is smaller than this one.

## L2. 6,089 review items is a large number and no framing shrinks it
Most are `FONT_FACE` (3,966) and `PROVENANCE_RIGHTS_GROUP` (1,880). The face items are
largely batchable; the provenance items are **not**, by design. The recommended path is not
to review 4,786 unverifiable fonts — it is to **disable them and rebuild from verified
sources**.

## L3. The review index is built from C3/C4 only
DIP-0B design units and C1/C2 AssetCandidates are **not** in the index, because they exist
only at pilot scale. When the corpus expansions run, `HISTORICAL_DESIGN_UNIT` and
`REUSABLE_ASSET` items will join it — the domains are defined and waiting, and the item
count will rise substantially.

## L4. Coverage percentages depend on category boundaries
"Reusable-material files" = 2,305 across six DIP-0A categories. Reasonable people could
draw that line elsewhere, which would move the 1.0%. The *count of audited files* (24) is
exact; the *denominator* is a judgement, and it is stated so the reader can check it.

## L5. The gates are contracts, not enforcement
`retrieval_gate()` and `automatic_use_gate()` are **pure predicates**. Nothing in DIP-0
calls them at a point of use, because there is no point of use — no retrieval path exists.
Wiring them in is DIP-1's job, and until then they describe the rule rather than enforce it.

## L6. Git is versioned history, not cryptographic immutability
Content hashes, an append-only validator, atomic writes, protected branches — but **no
commit signing** and no tamper-proof store. Evidential, not cryptographic.

## L7. Nothing is approved, and that is the point
0 approvals · 0 permission grants · 0 retrieval-enabled · 0 automatic-use-enabled ·
0 fonts installed · 0 files moved or deleted. The real ledger is **empty**.

DIP-0 produced the questions, the evidence, and the machinery to answer them safely.
**It answered none of them, and it was never supposed to.**
