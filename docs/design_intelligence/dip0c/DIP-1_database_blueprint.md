# DIP-1 — database blueprint

**A proposal. No models are implemented, and none should be until this is reviewed.**

## The one principle that governs everything

**Machine inference · evidence · human decision · operational permission live in FOUR
SEPARATE RECORDS.** They never share a table and never share a key.

That is not tidiness. It is the only structure in which:
- a human correction sits *beside* an inference rather than erasing it;
- "we found an OFL" can never become "we have a licence";
- and **a licence can never attach to a SHA-256 hash.**

## The load-bearing separation

> **`FontDuplicateGroup` (technical) and `FontProvenanceRecord` (rights) must NEVER be
> joined into one table or one permission source.**

An identical font file from two different sources has:
- **one** shared technical identity;
- **two** provenance records;
- **two** rights decisions;
- **two** operational permission states.

Join them and one package's paperwork silently clears an identical file from an unknown
source. That is the C4b defect, made permanent in a schema.

**No duplicate or family relationship may propagate legal approval.**

## Core source and provenance

| model | holds | never holds |
|---|---|---|
| `SourceFile` | path, SHA-256, size, format, mtime | rights, permissions |
| `SourcePackage` | package root, kind, credibility | permissions |
| `ProvenanceRecord` | **acquisition source**, original path, package, purchase/contract context | technical metadata |
| `TechnicalAudit` | parse status, warnings, capability tier | rights |
| `ParserRun` | parser name+version, config, run timestamp | conclusions |
| `ConfigurationVersion` | thresholds, taxonomy version, pinned to every decision | — |

## Historical memory (REFERENCE_MEMORY_ONLY)

`HistoricalDesign` · `HistoricalDesignPage` · `DesignUnit` · `DesignObservation` ·
`PaletteObservation` · `TypographyObservation` · `LayoutObservation` ·
`DielineObservation`

**Excluded by contract:** exact placement coordinates · complete layouts · reusable dieline
paths · copied artwork paths · template instructions · automatic reproduction.

## Reusable assets

`DesignAsset` · `AssetCandidate` · `AssetFamily` · `AssetRelationship` ·
`AssetDuplicateGroup` · `AssetTechnicalReadiness` · `AssetTag` · `AssetPermission`

**`AssetDuplicateGroup` is technical.** Same rule as fonts: it never carries rights.

## Brand and palettes

`BrandAsset` · `BrandMasterDecision` · `BrandVariant` · `ColorPalette` · `ColorSwatch` ·
`PaletteDecision` · `CanonicalAuthority` · `ScopeTaxonomy`

`CanonicalAuthority` carries **`authority_domain`** (`BRAND_MASTER` / `BRAND_PALETTE`) —
uniqueness is enforced **within** a domain, never across. `ScopeTaxonomy` is **versioned**
and **pinned to every decision**, so a taxonomy change can never silently reinterpret an
old approval.

`ColorSwatch` keeps **raw** and **derived preview** under separate columns. A preview never
becomes source truth.

## Fonts

`FontSourceFile` · `FontFace` · `FontCollection` · `FontFamily` ·
`FontFamilyRelationship` · **`FontDuplicateGroup`** · `FontSourcePackage` ·
**`FontProvenanceRecord`** · `FontLicenseEvidence` · `FontRightsDecision` ·
`FontScriptCoverage` · `FontTechnicalObservation` · `FontStyleObservation` ·
`FontPermission` · `FontQuarantineRecord`

`FontCollection` exists because **a file is not a font** — a `.ttc` holds N faces.
`FontScriptCoverage` must adopt the **C4a script ranges** (supplementary planes included),
not the BMP-only DIP-0A implementation.
`FontLicenseEvidence` carries `mentions_fonts` and `grants_permission: false`.
`FontStyleObservation` is heuristic, capped, and **may not influence rights**.

## Human review

`ReviewItem` (identity = **domain + subject**) · `ReviewQueueMembership` (**many-to-many**;
never creates an item, never carries a decision) · `ReviewDecision` (attaches to the
**item**) · `EvidenceRecord` · `BusinessAssertion` · `PermissionGrant` ·
`PermissionRevocation` · `ApprovalAttestation` · `DecisionEvent` ·
`CompoundDecisionEvent` · `Actor` · `ReviewerRole`

**`PermissionGrant` is per-flag.** No approval implies one. `CompoundDecisionEvent`
preserves the atomic conflict-resolution shape so a DB can execute it in a real
transaction.

## Three things DIP-1 must not do

1. **Do not let `fsType` become a permission field.** It is embedding metadata.
2. **Do not default any permission to true.** Fail closed.
3. **Do not read "no suspicion" as "clean."** *Not suspected* means *not examined*.
