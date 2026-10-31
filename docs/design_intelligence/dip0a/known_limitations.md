# DIP-0A — Known limitations and carried-forward requirements

Everything below is a *known* gap, deliberately left open. None of it blocks the
DIP-0A commit; all of it constrains DIP-0B/0C/0D.

## Carried-forward requirements

### R1 — Font review must scale (DIP-0C, mandated)

DIP-0A flags **7,361 of 7,586** files as `review_required`, of which **4,883 are
fonts**. That is technically correct — no font's licence is verified — but human
review must **not** require one manual decision per font file.

DIP-0C must let a reviewer approve or reject a **family or source batch** while
retaining file-level provenance, grouping by:

- source folder
- family (and `typographic_family`)
- version
- duplicate group
- licence-evidence group
- quarantine status

`reports/fonts.json` already emits `duplicate_family_map` (families whose files
span multiple paths) as a starting point. **Not implemented in DIP-0A.**

### R2 — Archive extraction is a separate controlled milestone

76 archives, 11.69 GB on disk, ~15.42 GB expanded. DIP-0A reads central
directories only: nothing was extracted or recursed into. Before any extraction:
review duplicate archives and storage requirements.

Notable: **`25.10.15.zip` and `25.10.15 (1).zip` are byte-identical 3.57 GB
archives** (7.14 GB, ~2.4× the entire historical design corpus). They are flagged
as probable redundant downloads and left untouched. Two further archives are
**0-byte failed downloads**. An archive's existence proves nothing about the
licence or approval of its contents.

### R3 — Palette ingestion contract (DIP-0C/DIP-1)

`COLOR_PALETTE` exists as a category, but no `.ase` parser does.
`Pantone_3519C.ase` is `parser_support = partial`, `retrieval_allowed = false`,
`automatic_use_allowed = false`. Its filename does not establish that it is an
official BBROSE palette.

## Method limitations

### L1 — `mixed_raster_vector` in the pilot is a size proxy

The pilot marks a historical design as mixed raster/vector when the `.ai` is
≥ 20 MB. DIP-0A never opens the artwork, so embedded raster content is **inferred
from file size, not observed**. Only DIP-0B's deep audit can confirm it. Declared
in `pilot_manifest.json → caveats`.

### L2 — Folder names are hints, never truth

Hint-derived categories (`PATTERN`, `BACKGROUND`, `ICON`, `MOTIF`,
`PRODUCT_REFERENCE`, `DIELINE_REFERENCE`) are capped at **0.55 confidence** and
their `source` is `folder_hint`. Structural fallbacks by media type sit at 0.40.
Any consumer must respect confidence; none of these are settled facts.

### L3 — Weak licence evidence is a heuristic

A `.txt` / `.html` / `.url` file sitting beside assets is treated as accompanying
documentation (`strength = weak`) even when its name carries no licence token.
Named-licence forms (`OFL`, `EULA`, `TOU`, `terms of use`, `Apache`, `copyright`,
`licence/license`, `personal use`) are `strength = strong`.

**Neither strength grants any right.** Association is nearest-ancestor folder
scope, which can over-attach in deeply nested bundles. `license_status` never
leaves `UNVERIFIED` / `PENDING_HUMAN_CONFIRMATION` without a human.

### L4 — `OUT_OF_SCOPE` mockup rule is subject-keyword based

Unrelated commercial mockups are excluded when the path matches *both* a mockup
token and an unrelated subject (`apparel`, `shirt`, `overall`, `work-suit`,
`safety`, `hoodie`, `garment`, `clothing`, `tub`, `sink`, `mechanic`).
Packaging-relevant mockups (paper bag, shopping bag) deliberately survive. Of the
48 excluded files, **23 are recommended `human_confirm_exclusion`** in
`reports/out_of_scope_review.csv`. Nothing is deleted.

### L5 — Ownership is inferred from filenames only

`BBROSE`-bearing filenames → `LIKELY_BBROSE_UNCONFIRMED`; `ATC LOGO.ai` /
`JOJIA LOGO.ai` → `UNCONFIRMED_THIRD_PARTY`. No file inspection, no metadata, no
provenance chain. Folder location is explicitly *not* used. Every brand and logo
record carries `ownership_unconfirmed` in `review_reasons`.

### L6 — Parser coverage

- **`.psd` (87)** — `partial`. Signature-verified only; layers never opened.
- **`.fon` (38)** — `unsupported`. Legacy Windows bitmap fonts; fontTools cannot
  read them. These are exactly the 38 font parse failures (4,845 / 4,883 parsed).
- **`.mp4` (24), `.xlsx` (1), `.xml` (1)** — `unsupported` by design.
- **`.ase` (1), `.avif` (3), `.gif` (1), `.ttc` (38)** — `partial`.
- All **226 `.ai` files are PDF-backed**; zero legacy PostScript. PyMuPDF can
  therefore parse every historical design in DIP-0B. The pre-audit flagged legacy
  PostScript as a risk — it is not present.

### L7 — Duplicate detection is exact-content only

Grouping is by SHA-256 over full file bytes; zero-byte files are never grouped.
**Near-duplicates, re-exports, resized variants and recompressed images are not
detected.** For archives, an additional *content-manifest* fingerprint
(sorted `name|uncompressed_size`) identifies probable duplicates whose container
bytes differ — 0 such groups found. The `canonical_candidate` (shallowest, then
shortest path) is a stable heuristic, **not a decision**: DIP-0A deletes,
moves and replaces nothing.

### L8 — Hash verification is sampled by default

`--full-hash-verify` re-hashes all 7,586 files (~23 s) and was used for the
recorded run. The default samples 50. The pre/post snapshot (size, `mtime_ns`,
inode of every file, junk included) always runs.

### L9 — Scope of the audit

DIP-0A produced **no embeddings, no semantic retrieval, no recipe generation and
no live-pipeline integration**, per the milestone definition. Nothing under
`materials/` was read for anything other than `stat`, magic bytes, SHA-256, zip
central directories and font tables.
