# Recommendations — DIP-0C4, DIP-0C5, DIP-1

## Before anything else: close the palette-conflict resolution gap

C3b4 shipped an atomic, validated resolution path for **master** conflicts. A **palette**
conflict is detected and fails closed — but resolving it today would need hand-written
events, because the seven resolution actions emit master event types.

The event types exist (`PALETTE_SUPERSEDED`, `PALETTE_DEPRECATED`). The guided atomic path
does not. **Close it before the first two palettes are approved** — with an empty ledger,
that is now, and it is cheap. See `c3d_known_limitations.md` §L5.

## DIP-0C4 — fonts

1. **Possession is not permission.** 4,883 font files. `fsType` embedding bits are
   *evidence*, not a grant.
2. **Batch by family and source**, never file-by-file — the only tractable review shape.
3. **Reuse the rights model wholesale.** Fonts need no new ownership vocabulary. They need
   licence-evidence association at family level and the same human-only gates. A font is
   a fourth authority domain (`TYPOGRAPHY_SYSTEM`) the moment a *brand* font is declared —
   the domain slot is already there.

## DIP-0C5 — consolidated review

4. **The queue registry is the spine.** Fourteen queues with stable IDs; C4 adds font
   queues to the same registry rather than a parallel one.
5. **Nothing becomes retrievable in C5.** It is a review milestone, not an activation one.

## DIP-1 — what must change when this leaves git

6. **Authenticated identity is the biggest gap.** Three dual-control gates now compare
   *asserted* actor IDs. "Two people" currently means "two names". Commit signing and
   DB-backed roles must land before any real approval is operationally relied upon.
7. **Transactional persistence.** The compound event was shaped as one validated
   transaction precisely so a database can run it inside a real one, with real isolation.
8. **Enforcement at point of use.** DIP-0C can *say* retrieval is false. It cannot yet
   *stop* anyone. Wire `effective_permissions()` — including the media axis — into the
   retrieval path so the answer has teeth.
9. **Grow the taxonomy by declaration, never by inference.** Every unregistered token fails
   closed into a queue: safe, and noisy. Registering markets, products and media as the
   business confirms them is the cheapest win available. Mind the sharp edge: a new
   *root* that actually contains an existing one would produce a wrong DISJOINT.
10. **The likeliest future mistake** is someone reading "canonical master" or "approved
    brand palette" as "safe to use". It never was, in either domain. Keep the axes apart.
