# DIP-0C4 — completion report

**Font intelligence: family grouping, licensing, provenance, batch review.**
Consolidates C4a (`2447a72`), C4b (`394ca3c` + correction `d18e1c7`) and C4c.

---

## The four statements that matter

1. **No font is approved, activated, installed, rendered, exported, embedded, exposed or
   retrievable.** Every permission is `false`.
2. **4,786 of 4,883 fonts (98%) have no licence evidence of any kind.**
3. **Exact bytes do not prove identical rights.** 941 duplicate groups → 1,880
   provenance-rights subgroups; **zero** are rights-batchable.
4. **The curated starter library cannot be built from what is here.** Arabic display, CJK,
   modern sans and elegant serif have **no candidate** that clears the bar.

## Scale

| | |
|---|---|
| font files | **4,883** (2.2 GB) |
| unique by SHA-256 | 3,941 |
| font **faces** | **3,966** — *a file is not a font* |
| technical families | 2,832 |
| source packages | 47 (46 credible + **1 duplicated dump**) |
| technical duplicate groups | 941 |
| provenance-rights subgroups | **1,880** |
| rights-batchable duplicate groups | **0** |
| review queues | 14 |
| distinct review units | **~1,400** |

## The twelve determinations

| | Answer |
|---|---|
| 1. same family? | name ID 16 (495 families) preferred; ID 1 (3,002) fragments by +2,507 |
| 2. duplicates? | 941 groups, 1,883 files — **technical identity only** |
| 3. source folders? | 46 credible packages; `Fonts`+`Fonts/3333` are **one dump, 92.5% identical** |
| 4. scripts? | latin 3,120 · arabic 248 · cjk 107 · thai 33 · hangul 19 (supplementary planes included) |
| 5. weights/axes? | full weight/width ladders; 16 variable faces (`wght`, `wdth`, `opsz`) |
| 6. healthy? | 3,966 faces parse; **32 `.fon` unsupported**, 0 failures |
| 7. system copies? | **706 faces / 669 files / 324 families suspected** — Microsoft 359, Monotype 196, Adobe 172 |
| 8. licence evidence? | 97 fonts have some; **only 72 have evidence that mentions fonts** |
| 9. recommendable? | **34 `CURATED_STARTER_CANDIDATE`s** — unapproved |
| 10. quarantined? | 1 proposal, 4,715 files — **proposed, not applied** |
| 11. batchable? | ~1,400 units. **Technical dedup does not reduce legal review** |
| 12. DIP-1 persistence? | 16 records — see `recommendations_dip0c5_dip1.md` |

## Three defects found and fixed — all mine

**CJK reported as Latin (C4a).** DIP-0A's script ranges cover the BMP only.
`mingliub.ttc` carries **42,711 codepoints in CJK Extension B** — a supplementary plane —
and **zero** in the BMP CJK block, so it reported as `latin` on the strength of 165 Latin
glyphs. Fixed with supplementary-plane ranges and per-script **counts**, plus an explicit
dominant script.

**Folder location was changing the answer (C4b).** `EV_DUMP_FOLDER` was weighted 0.0 — and
that wasn't enough. Its mere *presence* in the evidence list pushed **2,972 faces** out of
`NO_SYSTEM_FONT_EVIDENCE`, flagging them for **living in the wrong directory**. Outcomes now
depend on substantive evidence only.

**"Identical bytes are identical rights" (C4b).** The most dangerous sentence I wrote.
Rights attach to **provenance and acquisition**, not content — the same TTF bought under
licence and scraped from elsewhere is byte-identical and legally nothing alike. Corrected
in `d18e1c7`: duplicates split into one **technical identity** group and N
**provenance-rights** subgroups, and the "942 files saved" turned out to buy **no rights
review at all**.

## Two views, kept apart

**`TECHNICAL_FAMILY`** — which faces belong together, are they healthy? Answers *nothing*
about ownership, licence, permission or quarantine.
**`PROVENANCE_RIGHTS`** — where did each copy come from, what paperwork exists? Answers
*nothing* about family, weight, script or health.

**A decision in one never implies a decision in the other.** Tested.

## Six layers, never conflated

technical identity (SHA-256) → family grouping → source provenance → licence evidence →
**human rights decision** → **operational permission**.

**No layer grants the one below it.** A family is not a licence. An OFL is not a
permission. `fsType` is embedding metadata. **Possession is not permission.**

## Safety

**0** fonts installed · **0** rendered · **0** exported · **0** embedded · **0** exposed ·
**0** approved · **0** activated · **0** retrievable · **0** files moved · **0** deleted.
Every permission `false`, derived from the canonical `PermissionSet` — no count hardcoded.
Every human field blank. Machine inference immutable.

Guards raise on `LICENSE_APPROVED`, `COMMERCIAL_USE_APPROVED`, `APPROVED_BRAND_FONT`,
`BBROSE_OWNED_CONFIRMED`, `PERMANENTLY_REJECTED`, `APPROVED_FONT`, `ACTIVE_FONT`,
`RETRIEVABLE_FONT`, `PRODUCTION_READY_FONT`. **A machine may not condemn a font any more
than it may bless one.**

## Verification

| Check | Result |
|---|---|
| `pytest tools/dip0c` | **599 passed** (33 C4a + 45 C4b + 30 C4c) |
| DIP-0A + DIP-0B | **343 passed** |
| Django | **537 passed**, 1 skipped |
| `ruff check tools/` | clean |
| `materials/` integrity | **unchanged** |
| runtime | C4a 7.9 s · C4b 0.6 s · C4c 2.0 s |

## The decision that is not mine to make

**98% of the corpus has no licence evidence.** Clearing 4,786 fonts of unknown provenance
is not a review task — it is archaeology, and it would produce a library nobody can defend.

The recommendation is to **curate forward**: keep the dump disabled and archived, prioritise
the 46 organised packages, review the 72 fonts with font-relevant evidence, and rebuild from
sources with known provenance.

**And the capability gaps say the quiet part out loud: the starter library cannot be built
from what is here.** Arabic display, CJK, a modern sans and an elegant serif will have to be
**acquired** — properly, with paperwork. That is a business decision, and it is the most
consequential outcome of DIP-0C4.

**HOLD for final review before DIP-0C4 is declared complete.**
