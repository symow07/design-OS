# DIP-0C2a — Completion Report

**Slice:** AssetCandidate schema + capability-aware segmentation over the frozen
C2 pilot. **Status:** complete, held for review before DIP-0C2b.
**Scope guard:** segmentation and schema only. No technical-readiness scoring, no
pattern/watermark/perceptual/family logic, no reuse recommendation — those are
C2b–C2d. The five axes stay independent; nothing is granted; retrieval/automatic
use stay false; `APPROVED_REUSABLE` is unreachable from machine code; the DIP-0A
inventory is never rewritten.

Reproduce: `python -m tools.dip0c.run_c2a` (read-only). Per-candidate JSON →
git-ignored `var/…/dip0c/candidates/`; committed lightweight records → the frozen
`c2_pilot_manifest.json` + this report.

## C1 reference

DIP-0C1 commit: **`d0bf01ea1d8387ef0099bc97bb9d4c430f0725b4`**.
C2 pilot-manifest commit: **`6045fd613e6fbd84cd2f0bd25ac49bab2d18ab22`**
(one expectation corrected in this slice — see below).

## C2 pilot size and composition

20 frozen manifest entries → **19 unique source files** (5955567.ai serves two
roles — jpeg-shell and cross-format family — and is segmented once). Formats:
7 `.ai`, 5 `.eps`, 5 `.jpg`, 2 `.png`, 1 `.svg`.

## Expected vs actual (the payoff of freezing)

**All 19 files match their frozen `expected_segmentation_capability`.** Two
divergences were surfaced by this check *during* the slice and resolved rather
than shipped silently:

1. `344195-PC2FZA-950.ai` is a **2-artboard** file (the freeze probe checked page
   0 only). Corrected to `VECTOR_GEOMETRY_MULTI` / `multi_artboard_vector`; it is
   now the page/artboard-provenance fixture. (Recorded in the manifest notes.)
2. `raster_full_bleed` (`SL-041222` fluid background) first segmented into 5
   **AUTO_CONFIDENT** regions — a false-confident split of one background. Fixing
   the raster confidence rule (below) moved it to `AUTO_LOW_CONFIDENCE`, matching
   the frozen expectation.

## Candidates by method

**48 candidates** across 19 files.

| Method | Candidates |
|---|---|
| RASTER_CONNECTED_REGION | 25 |
| VECTOR_GEOMETRY | 13 |
| NONE (EPS header-only) | 5 |
| VECTOR_WHOLE_FILE_NATURAL | 3 (incl. JPEG-shell) |
| VECTOR_WHOLE_FILE_FALLBACK | 1 (0-cluster LOGO6) |
| SVG_ELEMENT_TREE | 1 |

## Segmentation-status totals

Candidate-level: `AUTO_LOW_CONFIDENCE` 21 · `SEGMENTED` 13 ·
`WHOLE_FILE_SINGLE_ASSET` 5 · `UNAVAILABLE` 5 · `AUTO_CONFIDENT` 2 ·
`MANUAL_REVIEW_REQUIRED` 2. File-level: `UNAVAILABLE` 5 · `SEGMENTED` 4 ·
`WHOLE_FILE_SINGLE_ASSET` 3 · `AUTO_LOW_CONFIDENCE` 3 · `AUTO_CONFIDENT` 2 ·
`MANUAL_REVIEW_REQUIRED` 2.

## Collection sheets successfully split

The metric is deliberately split three ways so a background is never mislabelled
a sheet:

- **Confident collection splits (3):** true-geometry vector splits —
  `9347862.ai` → 6, `9993170.ai` → 4, `260107-P4T7LC-198.ai` → 3. Only these are
  offered to the reviewer as confirmed multi-asset sheets.
- **Multi-artboard files (1):** `344195-PC2FZA-950.ai` → 2 per-artboard assets
  (a document with two artboards, not a sheet).
- **Low-confidence multi-region raster (3):** `5955566.jpg` → 13, `SL-041222` → 5,
  a transport photo → 3. Included in the review manifest **with a caveat** —
  regions may be parts of one composition, not distinct assets; a human confirms.

Every split candidate carries collection membership, its parent source and the
manual actions a reviewer may take (`split` / `merge` / `relabel` / `exclude`).

## Files remaining single candidates

**12** — including the two whole-file paths the scope distinguishes: `LOGO6.ai`
(segmenter yields 0 clusters → **fallback**, never zero) and the JPEG-shell
`5955567.ai` (a full-page embedded raster with few vector paths → **one**
embedded-raster asset, not fragmented into fake vector regions — the C1
JPEG-shell signal wired into segmentation), plus the single-subject PNG cutouts
(`AUTO_CONFIDENT`).

## Raster confidence: an honest boundary

The pilot proved that a fluid background (5 regions, big-mass 1.0, coverage 37 %)
and a genuine sticker sheet (13 regions, big-mass 0.94, coverage 54 %) are
**statistically indistinguishable** by connected-component stats. Geometry alone
cannot decide whether raster regions are distinct reusable assets or parts of one
composition. So the rule is conservative and honest: a single dominant region →
`AUTO_CONFIDENT`; **multiple** raster regions → `AUTO_LOW_CONFIDENCE` (a proposal
needing human confirmation); dense/unrepresentative (big-mass < 0.30) or
full-frame coverage → `MANUAL_REVIEW_REQUIRED`. Confident multi-asset splitting is
therefore a **vector-geometry** capability in C2a; raster multi-splits are
proposals.

## EPS preview-derived / unavailable

**0 preview-derived, 5 unavailable.** Every Illustrator TIFF preview in the pilot
is a 2-samples-per-pixel palette subset PIL cannot decode (`SyntaxError: unknown
pixel mode`), so a valid-but-undecodable preview is honestly **not a usable
preview** → `UNAVAILABLE`, with a single header-only whole-file candidate (bbox
from `%%BoundingBox`, capability `REQUIRES_TOOL`). EPS candidates carry **no**
geometry, editability, path, clipping or recolorability claims — verified by an
invariant. The `PREVIEW_DERIVED` path is real and exercised by a synthetic
decodable-preview EPS fixture in the tests.

## Raster low-confidence / manual

21 `AUTO_LOW_CONFIDENCE` candidates (multi-region proposals) and 2
`MANUAL_REVIEW_REQUIRED` (a dense raster pattern where big components carry only
8 % of the foreground, and a full-coverage case with no fg/bg separation).

## Parser failures

None.

## Invariants verified (all true)

`no_approved_reusable` · `retrieval_and_auto_use_all_false` · `no_rights_granted`
· `eps_no_geometry_claims` · `human_blocks_blank` · `candidate_ids_unique_per_file`
· `expected_vs_actual.all_match`. Candidate IDs are deterministic for identical
**source bytes + configuration** (the segmentation-threshold fingerprint is folded
into the id); the byte-identical exact-dup EPS pair legitimately shares an id
across two paths — a determinism signal C2c will use, not a collision.
`isolated_candidate_confidence` is populated on vector split candidates (a coarse
bbox-area-fraction proxy) and raster candidates (big-component mass).

## Runtime + output size

0.77 s over the pilot; committed footprint nil — 48 per-candidate JSON records
(~166 KB) stay in git-ignored `var/`.

## Verification

- `pytest tools/dip0c/tests` — **47 passed** (27 C1 + 20 C2a).
- Regression: DIP-0A + DIP-0B — **343 passed**; Django — **537 passed, 1 skipped**.
- `ruff check tools/dip0c` — clean.
- Materials snapshot **unchanged**; output resolves **outside** the source tree.

## Evidence requiring adjustment before DIP-0C2b

1. **EPS previews are undecodable by the current toolchain**, so no EPS asset can
   be segmented geometrically until Ghostscript C1B; C2b pattern/quality work must
   keep EPS at `REQUIRES_TOOL`, never claiming seamlessness or readiness from a
   header. A dedicated palette-TIFF preview decoder is a candidate future task.
2. **Raster multi-region splits are proposals, not confident assets.** C2b/C2c
   should lean on the confidence states + human review, and treat raster split
   *counts* as provisional. A real signal to separate "sheet of assets" from "one
   composition" (e.g. tile-regularity, colour coherence) is a C2b/C2c question.
3. **`segment_page` is dieline-tuned, not asset-tuned** — it drops low-path assets
   to zero (handled by the whole-file fallback) and its vector split granularity
   is not asset-optimised; treat vector split counts as provisional too.
4. **`asset_type` is deliberately `UNKNOWN_ASSET_TYPE`** for every candidate; type
   inference is C2b/C2c. "Candidates by type" is therefore not reported here.

**HOLD** for review before starting DIP-0C2b.
