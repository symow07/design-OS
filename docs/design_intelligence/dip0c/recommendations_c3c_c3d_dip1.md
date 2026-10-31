# Recommendations — C3c, C3d, DIP-1

## C3c — colour palettes (ASE)

1. **Build the tested ASE parser.** The DIP-0C probe confirmed `Pantone_3519C.ase` is
   `ASEF v1.0`, 66 bytes, one colour block — small but offset-fiddly, and my quick
   parser mis-stepped. Fixture-test it; do not guess.
2. **A palette is a scope-bearing asset like any other.** A Pantone book shipped with
   a licence is not BBROSE's to redistribute. Route palettes through the same
   ownership/licence axes — `Pantone_3519C.ase` starts `LICENSE_UNVERIFIED`,
   retrieval `false`.
3. **The filename is not the colour.** `Pantone_3519C` must be *parsed*, not believed.
   The C3a lesson (a filename never proves identity) applies unchanged.

## C3d — fonts

4. **Possession is not permission.** 4,883 font files; `fsType` embedding bits are
   *evidence*, not a grant. Batch by family/source, never one-by-one.
5. **Reuse the rights model wholesale.** Fonts need no new ownership vocabulary — they
   need `LICENSE_EVIDENCE` association at family level and the same human-only gates.

## DIP-1 — what must change when this leaves git

6. **Transactional persistence.** The compound event was deliberately shaped as one
   validated transaction so a DB can execute it inside a real transaction with real
   isolation. L6 (concurrent resolutions are not serialised) disappears the moment it
   does.
7. **Authenticated identity.** This is the biggest gap (L2). Dual control currently
   compares *asserted* actor IDs. Until identity is authenticated, "two people" means
   "two names". Add commit signing and DB-backed roles before any real approval is
   relied upon operationally.
8. **Enforcement at point of use.** DIP-0C can *say* retrieval is false. It cannot yet
   *stop* anyone. Wire `effective_permissions()` into the retrieval path so the answer
   has teeth.
9. **Grow the taxonomy deliberately.** Every unregistered token fails closed into queue
   D, which is safe but noisy. Registering markets/products as the business confirms
   them is the cheapest possible win — and mind L4: a new *root* that actually contains
   an existing one would produce a wrong DISJOINT.
10. **Do not un-gate retrieval on canonical status.** The most likely future mistake is
    someone reading "canonical master" as "safe to use". It never was. Keep the axes
    apart.
