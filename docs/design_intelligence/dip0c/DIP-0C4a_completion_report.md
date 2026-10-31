# DIP-0C4a — completion report

**Per-face font audit, TTC handling, family grouping, duplicates, scripts, variable
axes.** Builds on C3e (`a56109b`).

---

## The corpus, measured

| | |
|---|---|
| font **files** | **4,883** (2.2 GB) |
| unique by SHA-256 | **3,941** — 941 duplicate groups covering **1,883 files** |
| font **FACES** | **3,966** — *a file is not a font* |
| `.ttc` collections | 28 unique files → **85 faces** (every one carries more than one) |
| unreadable | **32 `.fon`** → `UNSUPPORTED_FORMAT`; **0** `PARSE_FAILED` |
| family review groups | **2,832** |
| variable fonts | 16 faces — axes `opsz`, `wdth`, `wght` |
| runtime | **7.9 s** |

## Two findings that reshape the milestone

### 1. The corpus is two populations, and folder is not a batch key

`Fonts/3333` (3,706 files) and `Fonts` (1,009) hold **4,715 of 4,883 files**, and
`Fonts` is **92% byte-identical** to `Fonts/3333`. They are not two batches; they are one
dump, twice.

The `DOWNLOADE 2026/*` packages (~168 files) *are* genuine batch units — and, not
coincidentally, they hold **all 47 strong and 50 weak licence-evidence associations** in
the entire corpus. The 4,715 in the dump have essentially none.

### 2. Family grouping does not solve batch review — and I will not pretend it does

**Only 21% of faces (840 of 3,966) carry name ID 16 at all.** 83% of groups are
singletons.

> **4,883 files → 3,966 faces → 2,832 review groups.**

That is a **42% reduction** in review units, not a batch-review solution. Determination
#11 is **not answered by family grouping alone**. The leverage must come from C4b —
a system-font suspicion that can retire the Windows population in one decision, and
licence evidence that can clear a download package at once. C4a made those batches
*possible*; it has not made them *small*.

## D2 was right, and the corpus proved it

**ID 16 yields 495 distinct families. ID 1 yields 3,002** — a fragmentation of **+2,507
spurious families**.

The concrete case: `SinkinSans-400Regular.otf` has ID 16 = `Sinkin Sans`, ID 1 =
`Sinkin Sans 400 Regular`. Under ID 1 an 18-file package explodes into 18 "families" of
one, and a reviewer faces eighteen decisions where there is one.

## Grouping safeguards, and what they caught

A group is never formed on a matching name alone. Each carries supporting **and**
conflicting evidence; conflicts flag rather than merge.

| Conflict | groups |
|---|---|
| `CONFLICTING_VENDORS` | 76 |
| `CONFLICTING_POSTSCRIPT_PREFIXES` | 70 |
| `DIVERGENT_VERSIONS` | 59 |
| `MULTIPLE_SOURCE_PACKAGES` | 27 |
| `INCOMPATIBLE_GLYPH_COVERAGE` | 5 |
| `GENERIC_FAMILY_NAME` | 1 |

**190 groups** are `FAMILY_RELATIONSHIP_REVIEW_REQUIRED`. Where vendors differ, the group
is **split by vendor**, not merged — two foundries' "Nova" is a coincidence until a human
says otherwise. Generic names (`Regular`, `Sans`, `Script`…) never merge unrelated fonts.

## A defect found and fixed: CJK reported as Latin

DIP-0A's script ranges cover the **BMP only**. `mingliub.ttc` carries **42,711 codepoints
in CJK Extension B** (U+20000–U+2A6DF, a *supplementary* plane) and **zero** in the BMP
CJK block — so under the inherited ranges it reported as **`latin`**, on the strength of
165 Latin glyphs.

A CJK font announcing itself as Latin is not a rounding error; it is the wrong answer, and
it would have mis-shelved every CJK family in the corpus. C4a defines its own ranges (CJK
Ext A–E, compatibility ideographs, Arabic presentation forms, emoji) and records each
script with its **codepoint count** plus an explicit **dominant script** — because presence
is not coverage.

Dominant scripts across the corpus: `latin` 3,120 · `arabic_presentation_b` 248 · `cjk`
107 · `thai` 33 · `arabic` 29 · `hangul` 19.

## Safety

`fsType` is recorded on every face — raw value, decoded flags, `is_permission: false`, and
a note saying **a font whose fsType says INSTALLABLE may still be one BBROSE has no right
to use.** Observed: `EDITABLE_EMBEDDING` 1,592 · `INSTALLABLE_EMBEDDING` 1,494 ·
`PREVIEW_AND_PRINT_EMBEDDING` 1,160 · `RESTRICTED_LICENSE_EMBEDDING` 843.

**No font was installed, rendered, embedded, exported, copied or exposed.** Enforced by a
test that walks the **AST** of every C4a module — the word "install" appears legitimately
in `INSTALLABLE_EMBEDDING`, so a substring grep would be theatre. Ownership, licence and
every permission remain untouched and `false`; C4a decides no rights and recommends
nothing.

## Verification

| Check | Result |
|---|---|
| `pytest tools/dip0c/tests/test_c4a.py` | **33 passed** |
| `pytest tools/dip0c` | see §regression |
| `ruff check tools/` | clean |
| `materials/` integrity | **unchanged** |
| committed output | `c4a_family_summary.json`, `c4a_reconciliation.json` (heavy per-face JSON → `var/`, git-ignored) |

## Next

**C4b** — system-font suspicion (from the name table, never the filename), licence-evidence
association, source-package grouping, rights and quarantine *recommendations*. That is where
the batch leverage has to come from, because family grouping did not deliver it.

**HOLD for review before C4b.**
