# DIP-0A — `materials/` master inventory

- Indexed files: **12473**
- Excluded junk (counted, not deleted): **189**
- Total indexed bytes: **114.80 GB**
- Duplicate groups: **1263** (1413 redundant copies, 9.48 GB redundant)
- Files flagged for human review: **12210**
- Symlinks recorded (never followed): 0

`materials/` was treated as read-only. Nothing was renamed, moved, converted, deduplicated or deleted. No generated output was written beneath the source root.

## Categories

| Category | Files |
|---|---|
| FONT | 5212 |
| RASTER_DESIGN_ASSET | 2219 |
| REUSABLE_VECTOR_ASSET | 1726 |
| PRODUCT_REFERENCE | 1604 |
| PATTERN | 459 |
| BACKGROUND | 400 |
| LICENSE_EVIDENCE | 261 |
| MOTIF | 190 |
| ICON | 107 |
| ARCHIVE | 94 |
| HISTORICAL_DESIGN | 91 |
| OUT_OF_SCOPE | 75 |
| UNKNOWN | 26 |
| LOGO | 4 |
| COLOR_PALETTE | 2 |
| BRAND_MASTER | 2 |
| SUPPORTING_METADATA | 1 |

## Parser support

| Status | Files |
|---|---|
| supported | 10760 |
| partial | 1249 |
| evidence | 261 |
| unsupported | 109 |
| archive | 94 |

## Extensions

| Ext | Files |
|---|---|
| `.ttf` | 3927 |
| `.jpg` | 3209 |
| `.ai` | 1272 |
| `.otf` | 1202 |
| `.eps` | 1196 |
| `.psd` | 543 |
| `.png` | 291 |
| `.txt` | 248 |
| `.jpeg` | 173 |
| `.zip` | 94 |
| `.svg` | 60 |
| `.pdf` | 50 |
| `.fon` | 38 |
| `.ttc` | 38 |
| `.mp4` | 25 |
| `.webp` | 18 |
| `.rar` | 17 |
| `.gif` | 17 |
| `.html` | 7 |
| `.js` | 7 |
| `.css` | 6 |
| `.avif` | 5 |
| `.url` | 5 |
| `.woff` | 4 |
| `.woff2` | 3 |
| `.ase` | 2 |
| `(no ext)` | 2 |
| `.xlsx` | 2 |
| `.log` | 2 |
| `.jpf` | 1 |
| `.ovpn` | 1 |
| `.psb` | 1 |
| `.rtf` | 1 |
| `.mov` | 1 |
| `.eot` | 1 |
| `.scss` | 1 |
| `.htm` | 1 |
| `.xml` | 1 |
| `.json` | 1 |

## Archives (manifest-only, never extracted)

- Archives: 94 (11.74 GB on disk, ~15.53 GB expanded)
- Encrypted: 0 · Corrupt: 0 · Suspicious: 0
- Exact duplicate archives: 2 groups
- Probable duplicates by content manifest: 0 groups

## Font quarantine

- Font files: 5212 (parsed 5174, failed 38)
- Quarantined under `materials/Fonts/3333`: **3706**
- All fonts start license_status=UNVERIFIED. Bundled licence text and fsType bits are recorded as EVIDENCE only and never grant embedding, redistribution or commercial-output rights. No font is installed, embedded or auto-used by DIP-0A.

## Pilot manifest

- All mandated requirements met: **True**
  - ✅ display_or_stand_design
  - ✅ chinese_annotations
  - ✅ high_complexity_vector
  - ✅ poor_filename_hygiene
  - ✅ mixed_raster_vector
  - ✅ easy_medium_hard_spread
  - ✅ official_brand_candidate
  - ✅ unconfirmed_third_party_logo
  - ✅ licensed_download_fonts
  - ✅ suspected_system_fonts

## Divergence from pre-audit estimates

- `indexed_files`: estimate 7586 → actual 12473
- `excluded_junk`: estimate 109 → actual 189
- `duplicates.groups`: estimate 1017 → actual 1263
- `duplicates.redundant_copies`: estimate 1046 → actual 1413

## Source-of-truth counts (supersede all earlier estimates)

- Indexed files: 12473
- Historical production designs: 91
- Total `.ai` files: 1272
- Exact-duplicate groups: 1263
- Redundant storage: 9.48 GB
- Font files: 5212 (quarantined: 3706)
- ZIP archives: 94
- Excluded junk files: 189

## Correction to the pre-audit estimates

The pre-audit reported **~18 GB of ZIP archives**. That figure was wrong. A *directory* is literally named `25.10.15.zip`, so `find -name "*.zip"` matched the directory and `du` recursed into it, double-counting the two 3.57 GB archives stored inside. The correct total, confirmed by `stat` and by this audit, is **11.74 GB**. The derived pre-audit claim of an "effective library of ~10 GB" was wrong for the same reason; the non-archive material is ~18.2 GB.

## Taxonomy (user-approved 2026-07-10)

- `ARCHIVE` — transport/storage container. Inventoried, hashed, manifest-inspected; excluded from retrieval and generation; never auto-extracted. Its existence is not proof that its contents are licensed or approved.
- `LICENSE_EVIDENCE` — supporting evidence linked to nearby assets/fonts. Never a reusable design asset; never auto-changes licence status.
- `SUPPORTING_METADATA` (subtype `FONT_METADATA`) — provenance / font-management sidecars. Traceable, never in design retrieval.
- `COLOR_PALETTE` — colour systems (`.ase` etc). Retrieval blocked until the DIP-0C/DIP-1 palette ingestion contract; auto-use blocked until parsed and human-approved.
- `OUT_OF_SCOPE` — understood and deliberately excluded. Distinct from `UNKNOWN`, which is reserved for genuinely unidentified files.

## Integrity

- Source tree unchanged: **True**
- Hash stability: sample:50 → stable=True
- Output outside source root: True
