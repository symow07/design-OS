# DIP-0C1 — Completion Report

**Slice:** frozen pilot · per-file technical audit · file-level reports.
**Status:** complete, held for review before DIP-0C2.
**Scope guard:** technical readiness only (axis A). No rights are decided, no
retrieval is activated, no `APPROVED_REUSABLE` is machine-emitted, and the
DIP-0A inventory is never rewritten — corrections are recorded as overrides.

Reproduce: `python -m tools.dip0c.run_c1` (read-only). Heavy per-file JSON goes to
`var/design_intelligence/audits/dip0c/` (git-ignored); only this report and the
frozen `pilot_manifest.json` are committed.

> **Vocabulary note (terminology correction, no result change).** The readiness
> value originally reported here as `READY_AFTER_RIGHTS_REVIEW` is now
> `TECHNICALLY_USABLE_WITH_CAVEATS` — the old name referred to the *rights* axis
> from inside the *technical* axis, which the two-axis rule forbids. This was a
> **rename only**: no classification logic, threshold, outcome, rights status,
> ownership status or eligibility changed, and every count below is byte-for-byte
> what the original C1 run produced (14 / 1 / 2 / 4 over 24 files). See
> [readiness_vocabulary_migration.md](readiness_vocabulary_migration.md).

## Pilot coverage

24 manifest entries (a few roles deliberately reuse one file, e.g. icon/EPS and
motif/collection-sheet), routed as:

| Kind | Count | Formats |
|---|---|---|
| PDF-backed vector (PyMuPDF) | 13 | 10 `.ai`, 3 `.pdf` |
| EPS (header-native C1A) | 3 | `.eps` |
| Raster / PSD | 4 | 2 `.jpg`, 1 `.png`, 1 `.psd` |
| SVG (native XML) | 1 | `.svg` |
| Deferred to later slice | 3 | `.ase` → 0C3; `.otf`, `.ttf` → 0C4 |

Every required coverage role is present: clean vector (high + medium complexity),
JPEG-shell `.ai`, vector + embedded raster, motif, pattern, background,
collection sheet, EPS with/without TIFF preview, raster background, transparent
PNG, PSD, SVG, brand master, third-party logo, licence document, presentation
deck, `.ase`, a licensed-download font, a quarantined font.

## Findings

**PDF-backed vector.** The "vector ≠ editable" trap is real and measured. The
JPEG-shell detector (embedded-raster coverage ≥ 85 % with few real paths) flagged
`5955567.ai` (19 paths, 116 % raster coverage) → `NEEDS_VECTOR_RECONSTRUCTION`.
`22719-NUGMUA.ai` (2 063 paths but 94 % raster) → `NEEDS_CLEANUP`. Clean vector
files (`3350475.ai` 13 881 paths; `9993170.ai` 1 426 paths) → editable,
`TECHNICALLY_USABLE_WITH_CAVEATS`. Beyond path/clip/group counts and raster coverage,
each record captures — from the single bounded xref sweep, no extra cost —
gradients (shadings), soft masks, transparency groups and tiling patterns
(`22719-NUGMUA.ai`: 13 soft masks, 11 transparency groups), plus off-canvas
geometry (40 partially-outside paths there). AI-private data is present on the
`.ai` files and is recorded as `REQUIRES_ILLUSTRATOR` (native semantics never
parsed). **Deferred within the PDF-backed audit** (not needed for axis-A
readiness, disclosed here like ASE/fonts): per-colourspace enumeration,
open-vs-closed path ratio, outlined-glyph vs live-text detection, and a rendered
raster preview.

**SVG.** Parsed natively via a hardened expat pass — not PyMuPDF. External-entity
resolution is blocked, an internal `<!ENTITY>` subset is rejected outright
(`REJECTED_UNSAFE_XML`), and scripts / `on*` handlers / `javascript:` URIs /
remote `href`s / `<foreignObject>` mark a file unsafe → `QUARANTINE`. The one
pilot SVG is clean (35 rect nodes) → `TECHNICALLY_USABLE_WITH_CAVEATS`, 0 unsafe.

**EPS header-native (C1A).** All 3 → `HEADER_AUDITED`. BoundingBox and (where
present) HiResBoundingBox parsed, process/spot inks and declared fonts read from
DSC comments, embedded-image and AI-private markers detected. **1 valid,
extractable TIFF preview** found (binary DOS-EPS; magic validated by seek, image
not extracted in C1). Geometry (paths/clips/groups/editability) is **not** claimed
— it is `REQUIRES_TOOL`, honestly the ceiling of a header-only pass.

**EPS Ghostscript adapter (C1B).** Implemented but **blocked**: gs is absent →
adapter status `BLOCKED_TOOL_UNAVAILABLE`, capability state
`GHOSTSCRIPT_NOT_INSTALLED`, no conversion attempted, no auto-install. The safe
invocation (`-dSAFER -dNOPAUSE -dBATCH`, network disabled, derivative dir under
`var/…/temporary/eps_pdf/`) is *recorded for review*, not executed. Even with a gs
binary present and `enable=True`, DIP-0C1 defers all conversion to the reviewed
converter pilot + fidelity gate. All 3 EPS require Ghostscript for geometry.

**Raster / PSD.** Dimensions, DPI, colour mode and alpha read DIRECT from headers
(pixels not decoded). Production art reaches 8333×8333 @ 300 dpi; a 558×546 RGBA
PNG → `REFERENCE_ONLY` (low resolution). PSD 8BPS header parsed for
dimensions/channels/depth/mode without decoding layers. `WATERMARK_SUSPECTED` is
HEURISTIC only (stock/preview filename hint **and** low resolution), never stated
as fact; low resolution alone never proves a watermark.

**Classification overrides (DIP-0A corrections, non-destructive).** 2 recorded:
`EULA Cartoon 2 US.pdf` (`REUSABLE_VECTOR_ASSET` → `LICENSE_EVIDENCE`),
`ATC PRESENTATION-1.pdf` (`REUSABLE_VECTOR_ASSET` → `THIRD_PARTY_RESTRICTED`).
Both keep `inventory_category_original` and leave `human_confirmed_category`
blank. `BBROSE-1.pdf` correctly stays `BRAND_MASTER` (no override).

## Totals

- **Technical readiness (axis A):** `TECHNICALLY_USABLE_WITH_CAVEATS` 14 ·
  `REFERENCE_ONLY` 4 · `NEEDS_CLEANUP` 2 · `NEEDS_VECTOR_RECONSTRUCTION` 1
  (deferred files carry no readiness).
- **Machine reuse-posture candidates:** `REUSABLE_AFTER_REVIEW` 19 ·
  `THIRD_PARTY_RESTRICTED` 2 · `BRAND_MASTER_CANDIDATE` 1 · `QUARANTINED` 1 ·
  `OUT_OF_SCOPE` 1. **`APPROVED_REUSABLE`: 0** (machine-forbidden, guarded + tested).
- **JPEG-shell:** 1 (`5955567.ai`). **TIFF previews extractable:** 1.
- **Parser failures / unsupported:** 0.

## Invariants verified

- No machine record contains `APPROVED_REUSABLE` (`machine_posture()` guard +
  full-record scan).
- Retrieval gate (`retrieval` / `automatic_use` / `embedding` / `production_use`)
  is off on every record regardless of technical readiness.
- Rights block defaults to false/unverified on every record; axis A never feeds
  axis B.
- Materials integrity: pre/post snapshot **unchanged**; output resolves **outside**
  the source tree.

## Verification

- `pytest tools/dip0c/tests` — **24 passed**.
- Regression: DIP-0A + DIP-0B — **343 passed**; Django — **537 passed, 1 skipped**.
- `ruff check tools/dip0c` — clean.
- Runtime 5.5 s over the pilot; committed-output footprint nil (heavy JSON stays
  in git-ignored `var/`, ~124 KB).

## Evidence requiring adjustment before DIP-0C2

1. **EPS geometry is unknown, not absent.** 3/3 pilot EPS (and ~536 in the
   library) yield rich headers but no geometry without Ghostscript. The converter
   pilot + fidelity gate is the gating dependency for any EPS editability verdict.
2. **Shared-file pilot roles.** A few files cover two roles; 0C2 segmentation
   (AssetCandidate) will treat a collection sheet as *many* candidates, so per-file
   readiness here is provisional for those.
3. **Spot-colour extraction on real EPS was often empty** (files use process CMYK
   or `%%CMYKCustomColor` without named separations); 0C2/0C3 colour work should
   not assume named spots from headers alone. The DSC parser now correctly folds
   *all* `%%+` continuation lines (a single-line-only bug was fixed and covered by
   a multi-line fixture), so multi-line spot lists in the full library are read in
   full.
4. **ASE + fonts are stubbed** (`DEFERRED`); the tested ASE parser (0C3) and font
   family/source grouping (0C4) remain to be built.

**HOLD** for review before starting DIP-0C2.
