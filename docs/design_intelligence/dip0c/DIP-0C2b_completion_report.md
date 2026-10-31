# DIP-0C2b — Completion Report

**Slice:** technical readiness (axis A), pattern analysis, raster quality,
watermark evidence. **Status:** complete, held for review before DIP-0C2c.

**Scope guard:** axis A is scored and **nothing else**. Rights (axis B), reuse
posture (axis C) and retrieval / automatic-use eligibility (D/E) are carried
through from C2a untouched — ownership `unconfirmed`, licence `unverified`, every
permission `false`. `APPROVED_REUSABLE` remains unreachable from machine code.

Reproduce: `python -m tools.dip0c.run_c2b` (read-only; re-runs C2a segmentation
in-process, so results never depend on stale `var/` artefacts). Thresholds are
pinned in [c2b_config.json](c2b_config.json) (readiness fingerprint
`1d8b92ce255f`); rationale in [c2b_decisions.md](c2b_decisions.md); standing
limits in [c2b_known_limitations.md](c2b_known_limitations.md).

## C2a reference

DIP-0C2a commit: **`5d77cf5cca80bb6f86f91de2069eadb4a809212b`**.
Readiness-vocabulary migration: **`50ec717721035034bb5fed5e098d10e9b191005b`**.

19 unique pilot files → **48 AssetCandidates** (unchanged from C2a; C2b scores
them, it does not re-segment differently).

## Candidates by technical-readiness recommendation

| Readiness | Candidates |
|---|---|
| `REFERENCE_ONLY` | 15 |
| `TECHNICALLY_READY` | 13 |
| `NEEDS_CLEANUP` | 9 |
| `TECHNICALLY_USABLE_WITH_CAVEATS` | 5 |
| `HEADER_ONLY_PARTIAL` | 5 |
| `NEEDS_VECTOR_RECONSTRUCTION` | 1 |

- **Requiring cleanup:** 9 — all from `COLLECTION_SHEET_AMBIGUITY` (low-confidence
  raster multi-region: regions may be one composition, not distinct assets).
- **Requiring reconstruction:** 1 — the JPEG-shell `5955567.ai`.
- **Blocked by tooling:** 5 — every real EPS candidate (`HEADER_ONLY_PARTIAL`).
- **Remaining reference-only:** 15 — small crops below the resolution floor.

## Pattern verdict totals

A repeat verdict describes a **tile**, so it is counted per **source** (a pattern
file that segments into motifs is still a tile as a whole). Crops out of a
multi-asset source are not tiles and return `REQUIRES_HUMAN` rather than a
fabricated verdict.

| Verdict | Sources | Candidates |
|---|---|---|
| `REPEAT_TYPE_UNCERTAIN` | 7 | 4 |
| `NON_SEAMLESS_LIKELY` | 6 | 4 |
| `REQUIRES_TOOL` | 6 | 6 |
| `REQUIRES_HUMAN` | 0 | 34 |
| `SEAMLESS_LIKELY` | **0** | 0 |

**No genuinely seamless raw tile exists in this pilot** — and that is a finding,
not a gap. The two files *named* as patterns (`260107-P4T7LC-198.ai`,
`00b8725f….jpg`) come back `NON_SEAMLESS_LIKELY`: they are showcase compositions,
not raw tiles. This is exactly the filename-is-supporting-evidence-only rule doing
its job. The `SEAMLESS_LIKELY` path is proven by synthetic fixtures (a wrapping
sinusoid scores 1.01 against a theoretical 1.00).

## Raster-quality bands

Measured on the **candidate crop**, not the parent file.

| Band | Candidates |
|---|---|
| `TOO_LOW` (<400 px) | 13 |
| `HIGH_RES_CANDIDATE` (≥2000 px) | 9 |
| `LOW_RES_REFERENCE` (≥400 px) | 2 |
| `SCREEN_READY` (≥1000 px) | 1 |

The 13 `TOO_LOW` are the small stickers cropped from the 2000² sheet — the parent
is large, the crops are not, which is precisely why the crop is what gets measured.
**Nothing is called print-ready from pixels alone** (`print_suitability =
UNDETERMINED_REQUIRES_PHYSICAL_SIZE`), and **low/absent DPI never rejects a
high-resolution file**.

## Watermark-suspected totals

**0 suspected.** No pilot file carries a stock-provider name, preview label,
periodic low-opacity overlay or edge text band. Low resolution alone contributes
nothing, so the 13 small crops are correctly **not** suspected — the false-watermark
case is pinned by a test. `NOT_SUSPECTED` is not a clearance; it means no positive
signal was found.

## Embedded-raster / JPEG-shell totals

**1 source:** `5955567.ai` — a full-page embedded raster with 19 vector paths →
`NEEDS_VECTOR_RECONSTRUCTION`. `22719-NUGMUA.ai`-style raster-heavy vector is
caught separately by `VECTOR_RASTER_BALANCE` → `NEEDS_CLEANUP`.

## Three bugs caught before shipping

0. **A page-level quality judgment was blocking clean sub-candidates.** The
   candidate assessor inherited source evidence with its `blocking` flag intact, so
   "raster covers 70 % of the *page*" propagated into every vector sub-cluster cut
   out of that page — including clusters sitting far from the embedded image, which
   are not themselves raster-heavy. That is precisely the "a poor parent invalidates
   a clean candidate" case the design forbids, and the original independence tests
   missed it because they called the merge helper directly instead of the real
   pipeline. Now a page-level judgment binds only the candidate that **is** that
   page (which is how the JPEG-shell verdict works); for sub-candidates the same
   evidence is carried as **non-blocking context**. Confirmed on a synthetic
   raster-heavy page with two clean clusters: source `NEEDS_CLEANUP`, clusters
   `TECHNICALLY_READY`. Pilot totals were unaffected (the pilot had no such file),
   which is exactly why it needed a constructed case. Both directions are now
   tested through `score_entry`, not the helper.

1. **12 false `SEAMLESS_LIKELY` verdicts.** Artwork floating in white space
   "wraps" trivially — any flat margin matches any other. A flat-margin vacuity
   guard now returns `REPEAT_TYPE_UNCERTAIN` for these.
2. **The seam metric and the half-drop probe were both wrong.** Normalising the
   seam by the *mean* gradient flunked a genuinely seamless tile (1.57); it is now
   normalised by the *local edge step*, where a perfect wrap scores ~1.0. And the
   half-drop probe rolled the tile and re-measured — which reproduces the same seam
   and proves nothing. It now compares the last column against a **rolled copy of
   the first column** (the neighbouring tile is what is offset). Measured: seamless
   1.01, visible seam 473, half-drop fails straight (163) but is perfect (0.00)
   under a half offset.

## Invariants verified (all true)

`no_approved_reusable` · `no_retired_readiness_vocabulary` ·
`readiness_vocabulary_canonical` · **`eps_never_technically_ready`** ·
`no_rights_granted` · `retrieval_and_auto_use_all_false` ·
`seamless_confidence_capped`. Readiness is deterministic (same bytes + config ⇒
same verdict, pinned by a test that runs the whole pilot twice). Source and
candidate verdicts stay independent except for safety/tool blockers — tested in
both directions.

## Test / lint / integrity status

- `pytest tools/dip0c/tests` — **98 passed** (27 C1 + 20 C2a + 11 migration +
  40 C2b).
- Regression: DIP-0A + DIP-0B — **343 passed**; Django — **537 passed, 1 skipped**.
- `ruff check tools/dip0c` — clean.
- Materials snapshot **unchanged**; output resolves **outside** the source tree.
- Runtime 2.1 s over the pilot; committed footprint nil (per-candidate JSON
  ~314 KB stays in git-ignored `var/`).

## Evidence requiring adjustment before DIP-0C2c

1. **EPS remains header-only.** 5/5 EPS candidates are `HEADER_ONLY_PARTIAL`;
   geometry, editability and seamlessness are **unknown, not absent**. C2c family
   grouping may use EPS filename/folder/exact-SHA evidence only — never geometry.
   (The byte-identical EPS pair already shares a candidate id, which C2c can use.)
2. **9 candidates are `NEEDS_CLEANUP` purely from collection-sheet ambiguity.**
   Their readiness will change once a human confirms whether the raster regions are
   distinct assets. C2c/C2d should treat these as pending, not as defective.
3. **15 `REFERENCE_ONLY` crops are small by construction**, not by defect — they
   are stickers cut from one sheet. If a human confirms the sheet is a genuine
   collection, the right fix is a higher-resolution re-crop from the source, not a
   quality downgrade.
4. **No seamless tile in the pilot**, so the `SEAMLESS_LIKELY` path is proven only
   synthetically. If C2c/C2d needs confidence in it on real data, the pilot needs a
   genuine raw tile added (with a recorded reason).

**HOLD** for review before starting DIP-0C2c.
