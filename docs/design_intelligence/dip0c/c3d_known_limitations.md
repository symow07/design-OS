# DIP-0C3d — known limitations

## L1. Actor identity is asserted, not authenticated — and now three dual-control gates lean on it
Unchanged since C3b2, and it carries more weight with every slice. Canonical dual
control, palette dual control and every attestation compare **actor IDs supplied by the
caller**. The system refuses an approval that only one *named* actor touched; it cannot
tell whether one human is behind two names. Commit signing, authenticated identity and
DB-backed roles are DIP-1. Until then, dual control is a strong procedural control, not
a cryptographic one.

## L2. Git is versioned history, not cryptographic immutability
Carried from C3b4 and unchanged. Content hashes, an append-only validator, atomic
compound writes, protected branches and reviewed PRs — but no commit signing and no
tamper-*proof* store. The audit trail is evidential, not cryptographic.

## L3. The media taxonomy is deliberately incomplete, and it will generate review items
Seven tokens. `SCREEN` vs `WEB` returns UNKNOWN, `DIGITAL` vs `WEB` returns UNKNOWN, and
so every scope touching `WEB` or `SOCIAL_MEDIA` fails closed into review. This is
correct — the business has not declared the hierarchy — but it means the media axis is
*noisy by design* until someone registers those edges. Do not "fix" it by guessing; fix
it by declaring.

## L4. Authority domains are a partition, not a lattice
`BRAND_MASTER` and `BRAND_PALETTE` never conflict with each other. That is right today.
But if a future domain genuinely *did* constrain another — say a `TYPOGRAPHY_SYSTEM` that
depends on a palette — nothing in the model expresses that dependency. Cross-domain
*consistency* is unmodelled; only cross-domain *non-interference* is. Adding a domain is
easy; adding a relationship *between* domains is a design question nobody has asked yet.

## L5. Palette conflicts have no atomic resolution path
C3b4 built `conflict_resolution.py` with seven actions and an atomic compound writer —
but its actions are named for masters (`SUPERSEDE_INCUMBENT` emits
`CANONICAL_MASTER_REPLACED`). A **palette** conflict is detected, fails closed, and lands
in queue `CANONICAL_CONFLICT` — but resolving it would today require hand-written events
rather than the validated compound path. The event types exist (`PALETTE_SUPERSEDED`,
`PALETTE_DEPRECATED`); the *guided, atomic resolution* for the palette domain does not.
**This is the sharpest gap in C3d.** It should be closed before any real palette conflict
can occur — which, with an empty ledger, means before the first two palettes are approved.

## L6. `check_approval` conflict detection is caller-supplied
It compares against an `existing_palettes` list the caller passes in, rather than
projecting the ledger itself. The *read model* (`canonical_read`) does project properly
and fails closed — so the safety property holds where it matters — but a caller who
forgets to pass `existing_palettes` gets no conflict check at that gate. The ledger-level
check is the one that binds; this one is belt-and-braces that can be forgotten.

## L7. The naive CMYK preview still exists, and is one careless import from misuse
`color_compare` refuses it, and there is a test. But `palette.normalize()` still *computes*
it, and nothing stops a future module reading `normalized.srgb_preview` directly and
comparing it. The gate protects the door, not the window. A stronger design would not
compute a preview it forbids comparing — deferred, because a reviewer genuinely needs to
*see* an approximate colour.

## L8. `Pantone_3519C.ase` cannot actually be approved, and that is correct
It fails on ownership, licence, evidence, unacknowledged PANTONE naming, an
unacknowledged parser fallback, and undeclared value provenance. All six are real. It
sits in three queues. Nothing in C3d makes it usable, and nothing should.

## L9. The corpus is still one palette
Every palette conclusion is about **one downloaded 66-byte file**. C3d builds the
machinery for palettes; it does not survey BBROSE's palette practice, because there is
nothing to survey.

## L10. Queue contents depend on machine findings passed in by the caller
`review_c3.build()` takes `brand_findings` from the caller rather than re-deriving them
from the C3a audit. That keeps the queue builder pure and deterministic (and testable),
but it means a runner that passes an empty `brand_findings` gets empty brand queues
without any error. The ledger-derived queues (conflicts, expiry, permissions) are always
correct; the machine-inference queues are only as good as what they are handed.
