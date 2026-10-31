# DIP-0C4c — decisions

## D1. Two views, structurally separate
`TECHNICAL_FAMILY` answers *"which faces belong together, and are they healthy?"*.
`PROVENANCE_RIGHTS` answers *"where did each copy come from, and what paperwork exists?"*.
Each carries an explicit `answers_nothing_about` field, and a test asserts the technical
view has no rights fields and the rights view has no typographic ones.

**A decision in one never implies a decision in the other.** This is structural, not a
note, because the C4b defect was exactly this conflation: exact bytes prove technical
identity and prove *nothing* about rights.

## D2. Machine inference is immutable
Every manifest row is `{machine, human}` — two blocks, disjoint keys. A human correction
is recorded **beside** the inference, never over it. A test writes a human correction and
asserts the machine block is byte-identical afterwards.

## D3. Style tags come from the font, never the filename
Evidence: `OS/2.panose`, weight/width class, glyph count, and the font's own subfamily
string (name IDs 2/17 — metadata, not a filename). `filename_used: false`.

**And most of this corpus declares nothing.** PANOSE is all-zeros ("unset") on the majority
of the free and indie fonts here. **1,184 faces get no tag at all** — and that is the
correct answer. A confident tag on a font that told us nothing would be worse than silence.

Confidence is capped at 0.6. `affects_license_or_permission: false`.

## D4. QUEUE ITEMS ARE NOT DECISIONS
Summing the fourteen queues gives **6,921 "decisions" for 4,883 files** — a number that
flatters nobody and misleads everybody, because one face appears in several queues at once
(a suspected system font in the dump is in queues B, E, G and H simultaneously).

The reconciliation says so explicitly rather than reporting the flattering sum. **Technical
deduplication reduces repeated *parsing*. It does not reduce *legal review*: 0 of 941
duplicate groups are rights-batchable.**

## D5. Technical and rights duplicates are DIFFERENT QUEUES
`FONT_DUPLICATE_TECHNICAL_GROUP` (batchable — identical bytes are identical bytes) and
`FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW` (**never batchable** — identical bytes are not
identical rights). Two questions, two queues. The C4b correction, made structural.

## D6. A curated candidate is a shortlist entry, not a library
`CURATED_STARTER_CANDIDATE` is the only machine state. `APPROVED_FONT`,
`APPROVED_BRAND_FONT`, `ACTIVE_FONT`, `RETRIEVABLE_FONT`, `PRODUCTION_READY_FONT` all raise.
Selection is on **provenance and technical health** — known package (never the dump),
font-relevant evidence present but **unreviewed**, no system-font suspicion, no family
conflict, clean parse. Never on taste.

**34 candidates. approved = false. activated = false. every permission = false.**

## D7. The capability gaps are the real finding
**Arabic display, CJK, modern sans and elegant serif have NO candidate that clears the
bar.** The starter library **cannot be built from what is here** — those fonts must be
acquired with provenance. That is the strongest possible argument for curating forward
rather than trying to clear a 4,715-file dump, and it emerged from the data rather than
from a preference.

## D8. Quarantine remains proposed
`is_applied: false`, `applied_by_machine: false`, `human_confirmation: null`. The report
states plainly: folder membership alone does not prove system-font status; system-font
suspicion does not prove illegal acquisition; quarantine is proposed, not executed.
