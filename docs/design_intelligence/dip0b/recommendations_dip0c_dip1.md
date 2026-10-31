# DIP-0C and DIP-1 recommendations

## DIP-0C — deep audit of the non-historical library

DIP-0B covered HISTORICAL_DESIGN only. DIP-0C should deep-audit the other categories, reusing the DIP-0A inventory and the read-only invariants:

- reusable vector assets, motifs, patterns, backgrounds, icons
- logos and brand masters (ownership never inferred from folder)
- fonts — with **batchable family/source review** (the DIP-0A lesson: 4,883 fonts cannot be one-by-one)
- colour palettes (`.ase`) and the palette ingestion contract
- licence evidence and asset ownership/restriction confirmation

## DIP-1 — persistence schema (recommend for review, do not finalise)

Derived from what proved measurable, with machine inference and human confirmation in separate tables:

| Entity | Holds |
|---|---|
| SourceFile | one historical .ai file; sha256, size, pilot flag, PDF/Illustrator version |
| HistoricalDesign | the design a file represents; SKU/product code + era + market (human-confirmed) |
| HistoricalDesignPage | one artboard/page; boxes (pt+mm), rotation, off-canvas summary |
| DesignUnit | a DesignUnitCandidate; bbox, type, confidence, primary/off-canvas, include-in-memory decision |
| TechnicalAudit | B1 per-page facts; path/raster/clip counts, separations, /All, capability tiers, truncation |
| PaletteObservation | per-unit bucketed colour; sRGB, ΔE spot match + tint, ambiguity flags, six-class membership |
| TypographyObservation | Level-A per text-like region; bounds, lines, scale, alignment, caps appearance; Level-B null |
| DielineObservation | page-level outcome + score + evidence channels, line-class counts, unit associations (many-to-many) |
| ReviewDecision | human confirmation; separate from machine inference, with reviewer/at/version/disposition/correction_reason |
| ProvenanceRecord | algorithm versions, thresholds fingerprints, parser, extraction timestamps for every inferred value |
| AssetOwnershipRestriction | ownership/licence/restriction fields (brand-owned, third-party, unverified); gates Design-Memory inclusion |

Every inferred column pairs with its ProvenanceRecord; every human-confirmable column is null until a ReviewDecision sets it. Nothing is marked reusable production artwork.

## Scale to all 91 files (estimate)

| Metric | Estimate |
|---|---|
| Pages | 98 |
| Units | 1254 |
| Paths | 2493972 |
| MANUAL_REQUIRED units | 176 |
| HIGH+MEDIUM review units | 1034 |
| Runtime (B1–B5, min) | 13.0 |
| var/ output (GB) | 0.34 |

**These are estimates from a deliberately non-random pilot.** the pilot was deliberately chosen for an easy/medium/hard spread, not at random high-complexity files were intentionally over-represented product-category and SKU-era balance across the remaining 77 files is unknown representativeness of the other 77 files is unverified — do not treat the 14-file pilot as statistically complete

