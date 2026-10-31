# DIP-0C4a — decisions

## D1. The unit is the FACE, never the file
28 unique `.ttc` collections carry **85 faces** — two or three each, with different
family names, different PostScript names, and (as `mingliub.ttc` proves) faces that
belong in **different family groups**. Every count, key and group is per-face. Reports
say "N files / M faces" and mean it.

`face_id` is content-derived: `sha256(file) + collection_index + PostScript name`. Two
copies of the same file yield the same face IDs — which is exactly what 941 duplicate
groups need.

## D2. Family key: name ID 16, falling back to ID 1 — and the corpus proved why
Measured on the real corpus: **ID 16 yields 495 distinct families; ID 1 yields 3,002.**
ID 1 would have fragmented the corpus by **+2,507 spurious families**.

The concrete case: `SinkinSans-400Regular.otf` has ID 16 = `Sinkin Sans` but ID 1 =
`Sinkin Sans 400 Regular`. Under ID 1, an 18-file package explodes into 18 "families"
of one, and a reviewer sees eighteen decisions where there is one.

All the other names are recorded as evidence (ID 1, 2, 4, 6, 17, vendor, version,
package, hash, collection index), because the key is a *hypothesis*, not identity.

## D3. Dedup runs BEFORE parsing
941 SHA-256 groups cover 1,883 of 4,883 files — `materials/Fonts` is **92%
byte-identical** to `materials/Fonts/3333`. Hashing first, parsing the 3,941 unique
files once and attaching the audit to every member is both the speed lever (**7.9 s for
2.2 GB**) and the thing that makes the duplicated dump collapse.

## D4. A family group is never formed on a matching name alone
A group carries **supporting evidence** (same ID 16 / ID 1, same vendor, same package,
same PostScript prefix, compatible glyph coverage, coherent weight ladder, shared
variable axes, exact-duplicate members) and **conflicting evidence** (different vendors,
multiple packages, divergent versions, conflicting PostScript prefixes, incompatible
glyph coverage).

Conflicts do not merge quietly. They produce `FAMILY_RELATIONSHIP_REVIEW_REQUIRED` —
**190 groups** on the real corpus — and where the vendors differ, the group is **split by
vendor** rather than merged. Two foundries' "Nova" is a coincidence until a human says
otherwise.

## D5. Generic names are not families
`Regular`, `Roman`, `Sans`, `Serif`, `Script`, `Display`, `Italic`, `Bold`… — these
describe a *style*, not a family. A generic key is split by vendor **and** package and
flagged `FAMILY_NAME_TOO_GENERIC`. Merging every font in the corpus called "Regular"
into one reviewable family would hand a human a decision built on nothing.

## D6. Script coverage needed the supplementary planes — and counts, not presence
DIP-0A's ranges cover the BMP only. `mingliub.ttc` carries **42,711 codepoints in CJK
Extension B** (U+20000–U+2A6DF, a supplementary plane) and **zero** in the BMP CJK
block — so under the inherited ranges it reported as **"latin"**, on the strength of 165
Latin glyphs. A CJK font announcing itself as Latin is not a rounding error; it is the
wrong answer.

C4a therefore defines its own ranges (CJK Ext A–E, compatibility ideographs, Arabic
presentation forms, emoji…) and records every script with its **codepoint count**, plus
an explicit **dominant script**. Presence is not coverage: a font with 8 Greek glyphs and
40,000 CJK ones "supports" both only in the most useless sense.

## D7. `fsType` is recorded, and it grants nothing
Every face carries its `fsType` raw value and decoded flags, with
`is_permission: false` and a note saying so. **A font whose fsType says INSTALLABLE may
still be one BBROSE has no right to use.** The OpenType spec calls it embedding metadata;
this project calls it evidence. Neither calls it a licence.

## D8. C4a acts on nothing
No install, no render, no copy, no subprocess, no network, no export. Enforced by a test
that walks the **AST** of every C4a module rather than grepping prose — the word
"install" appears legitimately in `INSTALLABLE_EMBEDDING` and in these very docstrings,
so a substring check would be theatre.
