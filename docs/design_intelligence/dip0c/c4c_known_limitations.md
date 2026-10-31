# DIP-0C4c — known limitations

## L1. The review workload is large, and no framing makes it small
**~1,400 distinct review units** once the overlap is removed — the dump quarantine (1, if
accepted as one), 46 packages, 941 cross-package duplicate rights reviews, 190 family
conflicts, 30 family-source conflicts, 32 unsupported, 34 curated candidates, plus the
evidence queues.

The single biggest reduction (accept the dump quarantine as one decision) is also the one
carrying the most risk. **There is no arrangement of this corpus that makes it quick to
review honestly**, and C4c does not pretend otherwise.

## L2. 1,184 faces carry no style tag, and that is honest but unhelpful
PANOSE is unset on most free and indie fonts. A reviewer looking for "a modern sans" will
find the tag missing on exactly the fonts they most need it for. Deriving it from outlines
(stem contrast, x-height, terminal shape) is possible and was **not** attempted — it is
real typographic analysis, not metadata reading, and it belongs in its own slice if it is
wanted at all.

## L3. Capability inference is crude
`_capabilities()` maps dominant script + style tag → capability slot. With PANOSE absent
on most candidates, `modern_sans` and `elegant_serif` show as **gaps** partly because the
*tag* is missing, not necessarily because the *font* is. The gap list is a floor, not a
census — it says "we cannot show you one", not "there is none".

## L4. Cross-package duplicate rights review is 941 items and cannot be batched
By design (that is the C4b correction), but it is the largest irreducible queue. Each is a
genuinely separate question: *the same bytes arrived twice; do we know where either copy
came from?* For the dump, the answer is no — 941 times.

## L5. The manifest is per-face; rights attach per-file-per-package
A `.ttc` with three faces from one dump copy produces three manifest rows sharing one
provenance record. The views keep this straight, but a reviewer reading the face manifest
alone could over-count the rights work. The rights view is the authority on rights work.

## L6. Nothing here is reviewed
34 candidates, 46 packages, 72 fonts with font-relevant evidence — **all UNREVIEWED**.
Every permission false. No font approved, activated, installed, rendered, exported,
embedded, exposed or made retrievable. **0 files moved. 0 deleted.**

C4c produced the questions. It answered none of them, and it was never supposed to.
