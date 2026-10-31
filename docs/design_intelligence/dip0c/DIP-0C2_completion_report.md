# DIP-0C2 — Milestone Completion Report

**Milestone:** AssetCandidate segmentation, technical readiness, relationships and
human review. **Status:** complete (C2a–C2d), held for milestone review before
DIP-0C3.

**The single most important sentence in this report:** *nothing has been reviewed,
nothing has been approved, and nothing is active.* Every human field is blank,
every permission is false, and no asset is retrievable or automatically usable.

| Slice | Commit |
|---|---|
| C2a — schema + capability-aware segmentation | `5d77cf5cca80bb6f86f91de2069eadb4a809212b` |
| readiness-vocabulary migration | `50ec717721035034bb5fed5e098d10e9b191005b` |
| C2b — technical readiness, pattern, quality, watermark | `5bdfe4bb77a8fa70f261708983cf766c1175c842` |
| C2c — duplicates, similarity, families, canonical | `f845582c199481a5ade414fffe46315edfd334a1` |
| C2d — review manifest, queues, reports | `2f2e5ee09c3d52089593b23c3eeeb3e477bddf0f` |

Frozen pilot: **20 manifest entries → 19 unique source files → 48 AssetCandidates.**

---

## The seven things C2 found, kept strictly apart

The completion report deliberately does **not** summarise these as "families".

### 1. Exact file duplicates — **1 group**

`5955564.eps` is byte-identical in two packages. Exact file duplication is kept
apart from visual equivalence: an `.ai`, `.eps` and `.jpg` may look identical and
are **never** exact duplicates, because their editability is completely different.
Nothing was deleted, replaced or consolidated.

### 2. Source relationships — **72 edges**

`FILENAME_FAMILY` 24 · `VERSION_SOURCE` 22 · `ALTERNATE_FORMAT_SOURCE` 18 ·
`SAME_DOWNLOAD_PACKAGE` 7 · `EXACT_FILE_DUPLICATE` 1. Grouped into **2
cross-format source families** and **5 source-package families**.

### 3. Collection membership — **6 collection groups**

Candidates segmented from one surface. **A collection group is NOT a duplicate
family.** A sticker sheet holds many independent assets, reviewed together, that
are in no sense substitutes for one another. All six of the pilot's components are
of this kind.

### 4. Candidate visual relationships — **0**

No `EXACT_VISUAL_DUPLICATE`, no `LIKELY_NEAR_DUPLICATE`, no colorway, crop, format,
scale, mirror or rotation relationship, and therefore **0 visual families**. This
is an honest pilot finding: the pilot contains no visually-equivalent candidate
pair. Every one of those paths is proven by synthetic fixtures with false-positive
controls; none was manufactured by loosening a threshold.

### 5. Unresolved relationships — **49 edges** (a review queue, not evidence)

`UNKNOWN_RELATIONSHIP` means *a comparison ran, the evidence was insufficient, a
human may clarify*. Grouped by shared reason so nobody inspects 49 pairs one at a
time:

| Reason | Edges |
|---|---|
| `CONFLICTING_HASH_EVIDENCE` (dHash and pHash disagree) | 24 |
| `EPS_VISUAL_CAPABILITY_UNAVAILABLE` | 24 |
| `CANDIDATE_VS_WHOLE_SHEET_MISMATCH` | 1 |

### 6. Unavailable comparisons — **6 EPS candidates**

Marked `VISUAL_COMPARISON_UNAVAILABLE` + `REQUIRES_TOOL`. **The absence of a hash
is not evidence of visual difference.** These are *uncomparable*, not *unrelated* —
their source/package relationships still stand.

### 7. Canonical nominations — **6**

One per component, each with a score breakdown, evidence and runners-up. Rights
evidence contributed **exactly zero** to every score. `human_selected_canonical` is
blank on all six. The machine **nominates**; it never selects.

---

## Technical readiness (from C2b, unchanged)

`REFERENCE_ONLY` 15 · `TECHNICALLY_READY` 13 · `NEEDS_CLEANUP` 9 ·
`TECHNICALLY_USABLE_WITH_CAVEATS` 5 · `HEADER_ONLY_PARTIAL` 5 ·
`NEEDS_VECTOR_RECONSTRUCTION` 1.

**Readiness never propagated through a family.** The cross-format family is the
proof: `5955567.ai` → `NEEDS_VECTOR_RECONSTRUCTION`, `5955566.jpg` →
`NEEDS_CLEANUP`/`REFERENCE_ONLY`, `5955564.eps` → `HEADER_ONLY_PARTIAL`. Three
members, three different verdicts, three different capabilities — even though the
`.ai` and `.jpg` are visually near-identical whole-source (dHash 1, pHash 2).

## Review manifest and queues

**48 manifest rows**, each a `machine` block and a **blank** `human` block that
share no keys — so a human decision can never overwrite machine inference.

**Priorities:** HIGH 24 · MEDIUM 19 · LOW 4 · OPTIONAL 1. Every priority carries
its reasons.

**Nine queues:**

| Queue | Items | Priority | Batchable |
|---|---|---|---|
| A exact duplicates | 1 | HIGH | yes |
| B collection groups | 6 | MEDIUM | no |
| C cross-format families | 2 | HIGH | no |
| D unknown relationships (3 reason-groups) | 49 | MEDIUM | yes |
| E canonical nominations | 6 | HIGH | no |
| F EPS comparison unavailable | 6 | MEDIUM | yes |
| G low-information evidence | 0 | MEDIUM | yes |
| H weak bridges | 0 | HIGH | no |
| I rights/ownership blocked | 18 | HIGH | no |

**Estimated human-review workload: 38 decisions if batched, vs 88 one-by-one.**

The largest HIGH bucket is queue **I**: 18 candidates that are technically strong
(`TECHNICALLY_READY` / `…WITH_CAVEATS`) but whose ownership is unconfirmed and
licence unverified. These are the most dangerous assets in the library precisely
because they *look* ready. They are not usable.

## Coverage limitation (recorded, not hidden)

Blocking buckets above **400 members** are skipped rather than expanded into O(n²)
pairs. **On this pilot none were skipped**, so coverage is complete and the
reconciliation says so. At full-library scale a large package or format bucket
*will* exceed the limit and would then be compared only via pHash bands — at which
point the relationship search must **not** be called complete. Every skipped bucket
records its member count and the exact number of pairs it did not generate.

## Recommendations for DIP-0C3

1. **Rights are now the bottleneck, not technique.** 18 technically-strong
   candidates are blocked solely on unconfirmed ownership. C3 (brand masters,
   logos, palettes, ownership) should start from queue I — that is where reuse is
   actually gated.
2. **ATC / JOJIA third-party material must stay quarantined.** C1 already flagged
   them; C3 must confirm they never reach a canonical nomination for BBROSE.
3. **The `.ase` palette and the 4,883 fonts are still stubs.** They were deferred
   through C1–C2 and are C3/C4 work.
4. **Do not let a canonical nomination become a rights signal.** The nomination
   score is technical-only by construction; C3 must keep it that way.

## Recommendations for DIP-1 (scaling)

The 400-member bucket skip is a **retrieval/indexing** problem, not a matching one.
Do **not** solve it by reverting to naive all-pairs. Recommended:

- **finer pHash banding** (more, narrower bands) to raise recall per band;
- **multi-index Hamming search** (several independent band tables, union the hits);
- **aspect-ratio and information-score subdivisions** to split oversized buckets
  along axes that correlate with real similarity;
- **folder/package partitions** so a huge package is chunked rather than skipped;
- **category-aware blocking** (never compare a font to a background);
- **disk-backed or database-assisted candidate generation** once the working set
  exceeds memory.

DIP-1 is also where the persistence schema for AssetCandidates, edges, groups and
human decisions belongs — with the machine/human separation preserved exactly as it
is here.

## Verification

- `pytest tools/dip0c/tests` — **150 passed** (27 C1 + 20 C2a + 11 migration +
  40 C2b + 31 C2c + 21 C2d).
- Regression: DIP-0A + DIP-0B — **343 passed**; Django — **537 passed, 1 skipped**.
- `ruff check tools/dip0c` — clean.
- **Materials snapshot unchanged**; output resolves outside the source tree.
- C2d runtime 6.3 s; heavy output (manifest, queues, groups) ~228 KB in git-ignored
  `var/…/dip0c/c2d/`.
- **Totals reconcile with C2c**: 48 candidates = 48 manifest rows; 6 C2c components
  = 6 C2d candidate groups.

## Invariants verified across the milestone

Machine code cannot emit `APPROVED_REUSABLE`. Retrieval, automatic use and
production use are false on every record. Ownership is unconfirmed and licence
unverified on every record. Readiness never propagates through a family. EPS is
never `TECHNICALLY_READY`. Collection groups are never labelled duplicate families.
`UNKNOWN_RELATIONSHIP` never becomes positive evidence. EPS is unavailable, never
unrelated. Canonical is nominated, never selected. Every human field is blank, and
no batch decision is applied automatically.

**HOLD** — DIP-0C2 is complete and awaits milestone review before DIP-0C3.
