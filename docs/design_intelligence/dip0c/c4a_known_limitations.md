# DIP-0C4a — known limitations

## L1. Family grouping does NOT solve batch review, and I will not pretend it does
This is the finding that matters most, and it is uncomfortable.

**Only 21% of faces (840 of 3,966) carry name ID 16 at all.** The other 79% fall back to
ID 1, which is usually the true family — but for a corpus of one-off display fonts, the
family *is* the font. The result:

> **4,883 files → 3,966 faces → 2,832 review groups.** 83% of groups are singletons.

That is a 42% reduction in review units, not a batch-review solution. Determination #11
("how can 4,883 fonts be reviewed by family/source batch rather than individually")
**is not answered by family grouping alone.**

The leverage has to come from somewhere else, and C4b is where it lives: a
system-font suspicion that can retire the Windows-font population in one decision, and
licence-evidence association that can clear a whole download package at once. C4a's job
was to make those batches *possible*; it has not made them *small*.

## L2. Source folder is not a batch key, for 96% of the corpus
`Fonts/3333` (3,706 files) and `Fonts` (1,009) hold 4,715 of 4,883 files between them,
and one is 92% a copy of the other. Two "folders" here are one dump, twice. The
`DOWNLOADE 2026/*` packages (~168 files) are genuine batch units — and, not
coincidentally, they are where **all 47 strong and 50 weak licence-evidence associations
live**. The corpus is two populations, and only the small one is shaped for review.

## L3. Glyph-coverage compatibility is a crude heuristic
`_coverage_compatible()` compares dominant scripts and requires ≥30% Unicode-block
overlap. It caught 5 genuinely incompatible pairings. It will also produce false
"incompatible" flags for a family that legitimately ships a Latin subset and a full CJK
cut. It **flags for review**; it never splits a group on coverage alone.

## L4. The generic-name list is hand-written and English
`GENERIC_NAMES` holds 24 English style words. A font family genuinely *called* "Display"
by its foundry will be flagged generic and split — annoying, and safe. A generic name in
another language will not be caught. It errs toward splitting, which costs review time
and never merges the unrelated.

## L5. `.fon` is unresolved, not solved
32 unique legacy Windows bitmap fonts (38 files) cannot be read by fontTools at all —
there is no sfnt to parse. They are `UNSUPPORTED_FORMAT` / `REQUIRES_HUMAN` and remain
in the corpus as an open question. A dedicated `.fon` parser is possible but was not
worth it for 32 files that are almost certainly Windows system fonts anyway — which C4b
will confirm or deny.

## L6. Vendor ID is 4 bytes of self-declared metadata
`achVendID` is whatever the font's builder typed. `MS`, `ADBE`, `GOOG` are meaningful;
`XXXX` and `????` (seen in the corpus) are not. It is **evidence**, and C4b will treat it
as a *suspicion* signal only, never as proof of origin.

## L7. Version strings are not comparable across foundries
`DIVERGENT_VERSIONS` fires (59 groups) whenever a family's members disagree on version.
That is often benign — two weights released at different times. It is a review flag, not
a defect claim.

## L8. Nothing here is a rights conclusion
C4a says what a font *is*. It says nothing about who owns it, whether it may be used, or
whether it should be quarantined. Ownership, licence and every permission remain
untouched and `false`. That is C4b and C4c, and no machine will decide it there either.
