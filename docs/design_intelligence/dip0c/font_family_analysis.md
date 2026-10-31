# Font family analysis — the TECHNICAL view

**This view answers: which faces belong together, and are they healthy? It answers
NOTHING about ownership, licence, permission or quarantine.**

## Grouping

**Name ID 16 preferred, ID 1 fallback.** Measured: ID 16 yields **495** distinct families;
ID 1 yields **3,002** — ID 1 would have fragmented the corpus by **+2,507 spurious
families**. `SinkinSans-400Regular.otf` has ID 16 `Sinkin Sans` but ID 1 `Sinkin Sans 400
Regular`: under ID 1 an 18-file package becomes eighteen "families" of one.

**Only 21% of faces carry ID 16 at all**, so 83% of groups are singletons. **2,832
review groups from 3,966 faces is a 42% reduction, not a batch-review solution.**

## A family name is a HYPOTHESIS, not identity

A group is never formed on a matching name alone. **190 groups** are
`FAMILY_RELATIONSHIP_REVIEW_REQUIRED`: conflicting vendors (76), conflicting PostScript
prefixes (70), divergent versions (59), multiple packages (27), incompatible glyph
coverage (5). Where vendors differ the group is **split**, not merged. Generic names
(`Regular`, `Sans`, `Script`…) never merge unrelated fonts.

## Style observations — heuristic, and mostly silent

2,782 faces carry a tag; **1,184 carry none**.
2,883 declare PANOSE. Tags come from `OS/2.panose`,
weight/width class, glyph count and the font's own subfamily string — **never a filename**
(`filename_used: false`).

Most of the free and indie fonts here zero out PANOSE, so many faces get **no tag at all**.
That is the correct answer: silence, not a guess.

Tags: body candidate 1220, sans 741, display 686, serif 507, condensed 171, handwritten 156, high contrast 142, monospace 91.

**Style never touches licence or permission.**

| queue_id | label | items | priority | batch? |
|---|---|---|---|---|
| `FONT_FAMILY_RELATIONSHIP_REVIEW` | A | 190 | MEDIUM | yes |
| `FONT_DUPLICATE_TECHNICAL_GROUP` | G | 941 | LOW | yes |
| `FONT_UNSUPPORTED_FORMAT` | K | 32 | LOW | yes |
| `FONT_PARSE_FAILURE` | L | 0 | LOW | yes |

