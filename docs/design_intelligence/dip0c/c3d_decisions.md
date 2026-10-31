# DIP-0C3d — decisions

## D1. `queue_id` is identity; the letter is a label
Code, tests, reports and future database rows key on `queue_id`. The `display_label` is
what a human sees at the top of a column and may be renumbered without a line of code
changing. This is not fastidiousness: **C3b4 already shipped queues lettered A–J with
different meanings**, and if letters were identity, C3d's "queue B" would silently
corrupt every reader of C3b4's. Queue IDs are asserted globally unique at import.

C3b4's committed artefacts are untouched and still reproducible; a test proves it.

## D2. `media` is a fifth, independent scope axis (taxonomy v1.1.0)
Products answer *what is being designed*. Media answers *where it may be used*. A
palette approved for `DIGITAL` is not approved for the press, and encoding media inside
the product tree would collapse two questions into one — exactly the conflation C3b4
spent its effort removing.

Done **now** because the real ledger is empty. An axis added against a live ledger is a
migration; added against an empty one it is free.

## D3. Media relations are declared, never guessed
`PRINT` ⊥ `DIGITAL` **only** because `disjoint_peers` says so. `PACKAGING_PRINT` ⊥
`DIGITAL` by **inheritance** from that declaration — which is sound (it follows
necessarily from a human's statement), not an inference from structure.

**`SCREEN` vs `WEB` is `SCOPE_UNKNOWN_OVERLAP`.** A web page is shown on a screen, and
until the business *says* whether `WEB` sits under `SCREEN`, guessing either way is
precisely the inference this taxonomy forbids. So `media` sets
`mutually_exclusive_roots: false` — media tokens are not assumed to partition the
world. It generates review items. That is the honest answer.

## D4. v1.0.0 scopes normalize media to `ALL` — and say so
A scope predating the axis gets `media = ALL` for comparison, tagged
`MEDIA_ADDED_BY_COMPATIBILITY_NORMALIZATION`, with the original taxonomy version
preserved. **The original scope object is never mutated**: a compatibility default is a
fact about our migration, not a fact any human asserted. New v1.1.0 decisions must
supply media explicitly or explicitly declare `ALL`; malformed input fails closed.

## D5. AUTHORITY DOMAINS — a palette and a logo master never conflict
This is the safeguard that stops the whole model producing nonsense. A brand palette and
a canonical logo master may both be authoritative for the same brand, product, market,
media and period **without contradicting each other**: one says which *colours* are the
brand's, the other says which *file* is. They answer different questions.

Uniqueness is therefore evaluated **within** a domain — `BRAND_MASTER` and
`BRAND_PALETTE` today, with room for `TYPOGRAPHY_SYSTEM` and others. Two palettes over
one scope **do** conflict. Two masters **do** conflict. A palette and a master do not.
Collapsing them into one undifferentiated bucket would manufacture a conflict out of two
perfectly compatible decisions.

The read-model machinery is shared; the domains stay distinct.

## D6. Palette decisions live in the C3b ledger — there is no palette system
Ten new event types join the existing 23. They reuse the append-only store, the content
hashes, the authorisation policy, the transition rules, the compound writer, the
permission set, and expiry. `BRAND_PALETTE_APPROVED` and `PALETTE_SUPERSEDED` join
`DUAL_CONTROL_EVENTS`. A second system would be a second place for the rules to drift.

## D7. Palette dual control: `color_reviewer_id != legal_reviewer_id`
`COLOR_AND_BRAND` (BRAND_ADMIN *or* DESIGN_REVIEWER) and `RIGHTS_AND_USE`
(LEGAL_REVIEWER **only**), from two **distinct actors**, then activation by
`BRAND_ADMIN` alone. The 21-item checklist is split so neither attester is *authorised*
to answer the other's half. One person holding both roles is still one person.

## D8. Approval never rewrites the technical audit
A human **may** approve a `PARTIAL_PARSE` file — but the approval must explicitly
acknowledge the limitation **with a reason**, and the parse status, layout, warnings and
fallback flag travel *with* the approval and survive it unchanged. Approving a file does
not make it well-formed.

Every approved swatch value declares its provenance: `RAW_SOURCE` / `DERIVED_PREVIEW` /
`MANUALLY_CONFIRMED`. **A derived preview does not become source truth by being
approved.** A human may confirm a value the parser only previewed — but then it is
*their* value, recorded as theirs.

## D9. Third-party naming must be acknowledged, not skipped
PANTONE naming blocks approval until a human acknowledges it **with a reason** — exactly
as an unacknowledged contradiction blocks a canonical approval. A name is not a licence,
and approving a palette does not resolve it.

## D10. Six independent questions, six independent gates
Parsing ⇏ association. Association ⇏ ownership. Ownership ⇏ licence. Licence ⇏ brand
approval. **Brand approval ⇏ any operational permission.** Each arrow has a test. The
last is the one people most want to skip.

## D11. The permission set is reused, and no count is hardcoded
`P.FLAGS is RM.PERMISSION_FLAGS` — asserted by test. Reports derive the flag list from
the schema, so adding a tenth flag cannot silently leave a report claiming nine.

## D12. `color_compare.py` is a gate, not an engine
It refuses naive CMYK→RGB comparison, ICC-less print comparison, Pantone names as IDs,
and ΔE from uncontrolled previews. A ΔE built on a naive preview has every trapping of a
measurement and none of the validity — it would be the most confident-sounding lie this
system could tell. `Pantone_3519C.ase` is **not** linked to Historical Design Memory.
