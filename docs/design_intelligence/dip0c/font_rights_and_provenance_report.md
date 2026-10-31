# Font rights and provenance — the RIGHTS view

**This view answers: where did each copy come from, and what paperwork exists? It answers
NOTHING about typographic family, weight, script or health.**

## EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS

A SHA-256 match proves the **files** are the same. It says nothing about where each copy
came from, what was signed to obtain it, or what that licence permits. The same TTF bought
under a paid licence and scraped from elsewhere is byte-identical and **legally nothing
alike**. **Rights attach to PROVENANCE and ACQUISITION, not to content.**

**941 technical duplicate groups → 1,880
provenance-rights subgroups. 0 are rights-batchable** —
because nearly every duplicate spans the unverified dump. **One package's licence never
clears an identical file from another source.**

## Licence evidence — proximity is not relevance

**97 fonts** have some nearby evidence. **Only 72** have evidence that actually *mentions
fonts*. **4,786 have none at all.**

`animal-bookmarks/License free.txt` opens *"This license only applies if you downloaded
this **vector**…"* — a stock-vector licence sitting beside a font. Same-directory is a fact
about the filesystem; whether the document governs the *font* is a fact about the *text*.

Types: `UNKNOWN_LICENSE_TEXT` 38 · `SIL_OPEN_FONT_LICENSE` 28 · `APACHE_LICENSE` 18 ·
**`DEMO_OR_TRIAL` 12** · `VENDOR_URL_ONLY` 7 · `README_OR_NOTES` 4.

**Evidence is evidence.** An OFL does not set `LICENSE_APPROVED`. `fsType` is embedding
metadata, not a licence. **Possession is not permission.**

## Fail-closed policy

Any font without **reviewed and accepted** rights evidence: `LICENSE_UNVERIFIED`, and
retrieval / automatic use / production use / embedding / redistribution all **disabled**.
That is **4,786 of 4,883 fonts**. Nothing is permanently rejected or deleted.

**"No system-font suspicion" is never "safe" or "licensed."** *Not suspected* means *not
examined*.

| queue_id | label | items | priority | batch? |
|---|---|---|---|---|
| `FONT_PROVENANCE_MISSING` | B | 3780 | HIGH | yes |
| `FONT_LICENSE_EVIDENCE_PRESENT` | C | 70 | MEDIUM | yes |
| `FONT_LICENSE_EVIDENCE_IRRELEVANT` | D | 23 | HIGH | yes |
| `FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW` | H | 941 | HIGH | **never** |
| `FONT_SOURCE_PACKAGE_REVIEW` | I | 46 | MEDIUM | yes |
| `FONT_FAMILY_SOURCE_CONFLICT` | J | 30 | HIGH | yes |

