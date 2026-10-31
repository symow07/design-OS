# DIP-0B — Historical Illustrator Design Deep Audit: consolidated report

Pilot: **14 files, 15 pages, 173 design units.** Read-only; `materials/` unchanged throughout.

> Historical designs are reference memory, not templates.
> No exact historical placement geometry becomes a reusable layout.
> No historical dieline path enters the production dieline engine.
> No font-family claims were made.
> No OCR was used.
> No path-level registration association was falsely inferred.

## Acceptance questions

### 1. What do the pilot Illustrator files contain?

Multi-unit production artwork: carton dielines, surface artwork, product photos, blank spec tables, colour-swatch strips, sticker sheets, legal/ingredient text and barcodes — often all on one page.

### 2. How many meaningful units were detected?

173 DesignUnitCandidates across 15 pages — 53 SURFACE_ARTWORK, 35 TECHNICAL_NOTES, 31 PRODUCT_PHOTO, 22 DIELINE_CANDIDATE, 20 SPEC_TABLE, 6 LEGAL_TEXT, 3 UNKNOWN, 2 COLOR_PALETTE_STRIP, 1 BARCODE.

### 3. Which data is DIRECT?

Page boxes (pt+mm, y-down), path/raster geometry and counts, shading/SMask census, `/Separation` inks incl. `/All` registration and their full-strength sRGB, OCG names, XMP, content-stream operators, live-text and font counts (both zero).

### 4. Which data is HEURISTIC?

region segmentation, candidate typing, dieline structure, ΔE spot-to-ink matching, artwork descriptors, Level-A typography — each carries confidence + evidence.

### 5. Which data requires Illustrator?

original layer hierarchy, artboard names, live text + font identities, symbols, live effects, appearance stacks, editable swatch library — all locked in `/AIPrivateData` (present in all 14, never parsed). See native_illustrator_requirements.md.

### 6. Which data requires human review?

68 HIGH + 91 MEDIUM priority units; 15 batch groups make this tractable.

### 7. How reliably can dielines be separated from artwork?

Yes, at the page level. 11/15 pages yielded a LIKELY_DIELINE_STRUCTURE, 1 BORDERLINE, 3 REJECTED. A dieline commonly spans several artwork candidates, so separation is a many-to-many overlay, not a clean partition — hence human confirmation.

### 8. How reliably can palette behaviour be described?

Per unit, coverage-weighted, in six strict buckets. 127 colours matched a PANTONE ink by ΔE (tint-ramp), 308 are present but unattributed (valid colour, no recoverable named ink), and 23587 near-black artwork paths are flagged ambiguous. Path-level ink association is unavailable, so all matching is heuristic.

### 9. How reliably can typography hierarchy be described?

Level A only (bounds, apparent lines, relative scale, hierarchy rank, alignment, spacing, capitalisation appearance, density). Level B (wording, language, font, style) is unavailable: all typography is outlined and no OCR was used.

### 10. What should enter Historical Design Memory?

Primary SURFACE_ARTWORK and PRODUCT_PHOTO units with a dominant colour (50 recommended). Everything stays reference memory.

### 11. What must remain excluded?

Spec tables, technical notes, barcodes, legal-text blocks, crop/registration material and purely technical dieline geometry (84 recommended for exclusion).

### 12. What must DIP-1 persist?

See recommendations_dip0c_dip1.md — 11 proposed persistence entities.

### 13. What must DIP-0C still audit?

Reusable vector assets, motifs, patterns, backgrounds, icons, logos, brand masters, fonts, colour palettes, licence evidence and asset ownership — none audited here (pilot is HISTORICAL_DESIGN only).

### 14. What does this imply for scaling from 14 to all 91 historical files?

Estimated ~1254 units and ~1034 review units across all 91 files — an estimate from a deliberately non-random pilot; see the sample-bias caveats.

## Flagged-black visibility

- Near-black artwork paths kept as artwork, flagged ambiguous: **23587**
- `/Separation /All` registration ink present at document level in 9/14 files; path-level association **unavailable** on this pilot.
- Ordinary black artwork was NOT removed from Design Memory because `/All` exists. The small `unresolved_or_ambiguous` bucket does not hide this: the flagged-black count above is the real ambiguity scale.

## Review priority

| Tier | Units |
|---|---|
| HIGH | 68 |
| MEDIUM | 91 |
| LOW | 3 |
| OPTIONAL | 11 |

## Include / exclude recommendation (never final)

| Recommendation | Units |
|---|---|
| RECOMMEND_INCLUDE | 50 |
| RECOMMEND_EXCLUDE | 84 |
| REVIEW_REQUIRED | 39 |

