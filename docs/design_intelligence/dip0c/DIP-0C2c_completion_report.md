# DIP-0C2c — Completion Report

**Slice:** duplicates, perceptual similarity, asset families, colorways, canonical
candidates. **Status:** complete, held for review before DIP-0C2d.

**Scope guard:** relationships are **evidence, never verdicts**. Family membership
propagates **no** readiness, ownership, licence, permission, retrieval eligibility,
automatic use or brand status. Canonical assets are **nominated, never selected**.
Invariants fail the run on any breach.

Reproduce: `python -m tools.dip0c.run_c2c` (read-only). Thresholds pinned in
[c2c_config.json](c2c_config.json) (hash fingerprint `5f31dc7c2e5b`, algorithm
`dhash9x8+phash32x8+shape/1.0`); rationale in [c2c_decisions.md](c2c_decisions.md);
limits in [c2c_known_limitations.md](c2c_known_limitations.md); pilot figures in
[c2c_pilot_relationships_summary.json](c2c_pilot_relationships_summary.json).

## C2b reference

DIP-0C2b commit: **`5bdfe4bb77a8fa70f261708983cf766c1175c842`**.
19 sources → 48 AssetCandidates (unchanged; C2c relates them, it does not rescore).

## Exact duplicate groups

**1 source-level exact-duplicate edge** — `5955564.eps` exists byte-identically in
two packages. Exact duplication is kept strictly apart from visual equivalence: an
`.ai`, `.eps` and `.jpg` may look identical and are **never** exact duplicates
(they have entirely different editability). Nothing was deleted, replaced or
consolidated.

## Perceptual comparisons vs naive pair count

| | |
|---|---|
| Naive all-pairs (N²/2) | **1,128** |
| Pairs after blocking | **448** (60.3 % reduction) |
| Perceptual comparisons actually performed | **332** |

Blocking: exact-SHA groups · pHash 4×16-bit bands (LSH) · filename-normalized
stems · folder/package groups · aspect-ratio + format buckets. No database and no
vector index was built.

## Relationship totals

**Source-level:** `FILENAME_FAMILY` 24 · `VERSION_SOURCE` 22 ·
`ALTERNATE_FORMAT_SOURCE` 18 · `SAME_DOWNLOAD_PACKAGE` 7 · `EXACT_FILE_DUPLICATE` 1.

**Candidate-level:** `COLLECTION_MEMBER` 115 · `UNKNOWN_RELATIONSHIP` 49.

- **Near-duplicates: 0** (`EXACT_VISUAL_DUPLICATE` 0, `LIKELY_NEAR_DUPLICATE` 0).
- **Hypotheses: 0** — crop 0 · colorway 0 · format 0 · scale 0.
- **Mirrored/rotated matches: 0.**
- **Unhashable candidates: 6** (the EPS candidates — no perceptual comparison).

**Zero relationships beyond collection membership is an honest result, not a
gap.** The pilot simply contains
no true visual duplicate *candidate* pair. Every relationship path
(near-duplicate, colorway, crop, format, scale, mirror, rotation, silhouette
rescue) is proven by synthetic fixtures with false-positive controls.

## Family components and weak bridges

**6 components**, sizes `[13, 6, 5, 4, 3, 3]` — all driven by `COLLECTION_MEMBER`
(candidates segmented from one surface). **0 weak bridges** were needed on this
pilot; the split mechanism is proven by a synthetic `A~B~C~D` chain where a weak
sole-connector correctly splits `D` off rather than fusing it into the family.

## Canonical-candidate nominations

**6** — one per component. Each records the score breakdown, evidence, runners-up,
and a `rights_context` block that contributed **exactly zero** (`rights_contribution: 0`).
`human_selected_canonical` is blank on every one.

## Cross-format family `5955564` / `5955566` / `5955567`

| Member | Candidates | Readiness | Perceptually hashable |
|---|---|---|---|
| `5955567.ai` | 1 | `NEEDS_VECTOR_RECONSTRUCTION` | yes |
| `5955566.jpg` | 13 | `NEEDS_CLEANUP`, `REFERENCE_ONLY` | yes |
| `5955564.eps` | 2 | `HEADER_ONLY_PARTIAL` | **no** |

- **Source relationships found:** all five — `EXACT_FILE_DUPLICATE`,
  `FILENAME_FAMILY`, `ALTERNATE_FORMAT_SOURCE`, `VERSION_SOURCE`,
  `SAME_DOWNLOAD_PACKAGE`.
- **Visual corroboration:** `5955567.ai` vs `5955566.jpg` are near-identical
  whole-source (**dHash 1, pHash 2**) — the same artwork in two formats.
- **`readiness_did_not_propagate: true`** — the three members keep three different
  readiness values and three different capabilities.
- **Candidate equivalence deliberately NOT asserted:** the `.jpg` is segmented into
  stickers while the `.ai` is a single whole-page embedded-raster candidate, so no
  candidate pair is a comparable unit (a sticker is not the whole sheet). The visual
  link is true of the **files** and is recorded as source evidence; it is not
  promoted to candidate equivalence.

## False-positive controls

- Unrelated images → **no edge** (tested).
- Two blank images with **identical hashes** → never a confident near-duplicate;
  weak-evidence flag set and confidence capped (tested).
- Same folder + same filename stem + visually unrelated → **no equivalence**
  (tested) — candidate equivalence is never inferred from source facts.
- Same geometry + same palette → a duplicate, **not** a colorway (tested).

## Four bugs caught before shipping

0. **`POSSIBLE_CROP_VARIANT` fired from a shared folder with ZERO visual
   evidence.** Crop was the one hypothesis not gated on visual similarity
   (`not aspect_close and (same_pkg or geom_close)`), so two unrelated images that
   merely sat in the same download folder, with different aspect ratios, were
   related as crop variants. It fired **3 times on the pilot**, on pairs measured
   at dHash 22–30 / pHash 24–30 — wildly unrelated — and those false positives were
   about to be reported as a finding. This is precisely what "do not infer candidate
   equivalence from shared folders / same package" forbids. A crop now requires
   positive **containment** (the crop's hash matching one of the parent's region
   hashes), with **both** hashes agreeing within the strong threshold — a single
   lenient dHash was not enough, because on flat-background artwork two *unrelated*
   white-ish regions collided at Hamming 8 and manufactured a claim. Crop variants
   drop to **0** on the pilot, which is the honest result. The old tests missed this
   because the crop fixture was a genuine crop of the same image, and the
   unrelated-images control put them in *different* folders — neither exercised
   "unrelated + same folder", the path the pilot actually hit. That test now exists.

1. **24 spurious "colorways."** `geom_close` used `min(dHash, pHash)`, so a single
   agreeing hash carried a pair while the other strongly disagreed — pairing
   different stickers on one sheet as colorways. Changed to `max()`, matching the
   locked rule that **both** hashes must agree. They dropped to 0.
2. **The entropy floor condemned flat vector artwork.** A 2.0-bit floor marked a
   3-colour logo (~1.2 bits) as "weak evidence" — poisoning nearly every path. It
   is variance, not entropy, that identifies a blank image; the floor is now 0.5
   bits (degenerate images only).
3. **Silhouette-only matches fell off the graph.** The same logo on white vs black
   has nearly inverted grayscale hashes but an identical silhouette, and produced
   *no hypothesis at all*. Such pairs now stay on the graph as
   `UNKNOWN_RELATIONSHIP` / review — never promoted to a duplicate, because the
   pixels genuinely do differ. The palette signature is now measured over the
   **foreground** for the same reason: a shared white background was drowning a
   red-vs-blue difference (0.22, below the 0.25 threshold) that should be obvious.

## Invariants verified (all true)

`no_rights_or_permissions_propagated` · `no_automatic_canonical_selection` ·
`no_approved_reusable` · `no_retired_readiness_vocabulary` ·
`candidate_edges_have_blank_human_field` · `no_naive_all_pairs`.

## Tests / lint / runtime / integrity

- `pytest tools/dip0c/tests` — **129 passed** (27 C1 + 20 C2a + 11 migration +
  40 C2b + 31 C2c), including a full-run determinism assertion.
- Regression: DIP-0A + DIP-0B — **343 passed**; Django — **537 passed, 1 skipped**.
- `ruff check tools/dip0c` — clean.
- Runtime **5.4 s**; heavy output **223 KB** in git-ignored `var/…/dip0c/c2c/`.
- Materials snapshot **unchanged**; output resolves **outside** the source tree.

## Findings requiring changes before C2d

1. **EPS is invisible to every visual signal** (6 unhashable candidates). C2d's
   human-review batching must group EPS by source/package evidence, never expect a
   visual grouping, and must not present EPS as "unrelated" when it is merely
   uncomparable.
2. **The pilot has no true visual duplicate candidate pair,** so near-duplicate,
   colorway, mirror and rotation totals are all 0 on real data. If C2d needs
   confidence in these on real material, the pilot needs a genuine duplicate/variant
   pair added (with a recorded reason).
3. **All 6 family components are collection-membership groups,** not duplicate
   families. C2d's review batching should treat "members of one sheet" and "variants
   of one artwork" as different review tasks — they currently look alike in the
   component list.
4. **Large blocking buckets (>400 members) are skipped**, so at library scale a
   very large folder would be compared only via pHash bands. A real recall gap to
   close before running C2c on all 7,586 files.
5. **49 `UNKNOWN_RELATIONSHIP` edges** are the real human-review queue. C2d should
   prioritise these by confidence and by whether a silhouette or source-evidence
   signal is present, rather than presenting them as a flat list.

**HOLD** for review before starting DIP-0C2d.
