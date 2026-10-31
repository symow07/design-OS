# Font intelligence — DIP-0C4

**`COMPLETE_FULL_CORPUS`: 4,883 / 4,883 font files (100%).**

4,883 files → 3,941 unique → **3,966 faces** → 2,832 families → 47 packages.

## The findings

- **706 faces / 669 files / 324 families** are `SUSPECTED_SYSTEM_FONT_COPY` — from the
  **name table**, never the filename. Microsoft 359 · Monotype 196 · Adobe 172.
- **`materials/Fonts` is 92.5% byte-identical to `materials/Fonts/3333`** — one dump, twice.
- **97 fonts have licence evidence. Only 72 have evidence that mentions fonts.
  4,786 have none.**
- **EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS.** 941 duplicate groups → **1,880
  provenance-rights subgroups**; **zero** are rights-batchable.
- **34 curated starter candidates** — and **Arabic display, CJK, modern sans and elegant
  serif have NO candidate that clears the bar.** The starter library **cannot be built from
  what is here**.

## The recommendation

Keep the dump **operationally disabled** and **archived**. Prioritise the 46 organised
packages. Review the 72 fonts with font-relevant evidence. **Acquire the missing
capabilities from sources with documented provenance.** Rebuild the library forward.
