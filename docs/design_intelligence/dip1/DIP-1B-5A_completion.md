# DIP-1B-5A completion report

## Accepted lineage and migration

- DIP-1B-4B: `ea497119783f212bfdefb9757b704d8a9fd33200`.
- DIP-1B-5A migration commit:
  `1212439109e2d9177d2d2e2cef8f79d36a2fb2bb`.
- DIP-1B-5A implementation: this commit.

Migration `intelligence/0006_design_asset_dataset_scope.py` removed
`intel_asset_c2_dataset_only` and added `intel_asset_dataset_supported`. Its exact
allowlist is:

- `dip0c2_asset_candidate_pilot/1.0`;
- `dip1b_curated_asset_expansion/1.0`.

Before migration, all 47 DesignAssetProfile rows used the C2 identifier. SQL inspection
showed only one CHECK-constraint drop and one CHECK-constraint add, with no DML, table,
column, or unrelated alteration. Forward `0005 → 0006`, rollback before expansion,
and reapply passed. Existing C2 rows and identifiers did not change. After expansion,
reversing 0006 requires a separately approved bounded data reversal; the database must
fail rather than delete or relabel expansion history.

The strict two-value allowlist is correct for this MVP. Before a third production asset
dataset, review a controlled immutable `DatasetDefinition` registry so every future
dataset does not require another migration. This is a non-blocking future design note,
not part of DIP-1B-5A.

## Deterministic evidence

- dataset/schema: `dip1b_brand_evidence/2.0`;
- dataset SHA-256:
  `7f887093fc8acec25eb31680be909df92580bf06f226732c7d717ef1db34032e`;
- binding-manifest SHA-256:
  `c1f1f398e47654b22037219f92d4e8ee0fdddb8340f34bb4d337af3d7ffdf23e`;
- original expected C3a SHA-256:
  `dfccbad26e98744e78d606fec85a301a9d3d2357ff17cf8ece5fcbe7a2d9e62b`;
- stale ignored-output SHA-256:
  `b4a891debabebdb721b919fa793264c5e8c2e671f5e2d5f3e5218e284d2f5cbf`.

All 21 candidates are `PARTIALLY_VERIFIED`, technical-evidence-ready, and not ready in
the brand-identity, rights, palette-authority, or governance dimensions.

## Curated expansion

`dip1b_curated_expansion_manifest/1.0` has SHA-256
`8855cdb3856b2312a168aa0fca113604c2662e549f15378f4a8a2c5f644b1ba5` and exactly
59 entries: 6 historical designs and 53 design assets. No font or brand candidate was
added. The bounded import batch is `0b8638ec-3dbc-45c9-b0de-50b4d6b8bb92`.

| Record | Before | After |
| --- | ---: | ---: |
| CorpusItems | 117 | 176 |
| HistoricalDesignProfiles | 14 | 20 |
| DesignAssetProfiles | 47 | 100 |
| C2 DesignAssetProfiles | 47 | 47 |
| Curated-expansion DesignAssetProfiles | 0 | 53 |
| FontFaceProfiles | 34 | 34 |
| BrandCandidateProfiles | 22 | 22 |
| SourceArtifacts | 79 | 139 |
| SourceLocationObservations | 81 | 141 |
| ImportBatches | 3 | 5 |
| ImportRecords | 783 | 923 |

The 59 curated inputs had 59 distinct physical hashes. Historical designs remain
`REFERENCE_MEMORY_ONLY`, with no template or copied-layout eligibility. Every new asset
has a stable semantic key, exact source hash and locator, vector technical readiness,
manifest provenance, and `THIRD_PARTY_RIGHTS_UNREVIEWED`. That warning blocks any
inference of ownership, licence, or use permission.

The unchanged-input second apply reused the completed batch, created no row, reported
59 unchanged semantic records, and created no new source version.

## Review set and browser

`dip1b_curated_review_manifest/1.0` has SHA-256
`84e881191af252fd0d6767f9951a8904187168e1ce5c082d231094762ad0b72a` and selects:

- all 6 added historical designs;
- 24 strongest added design assets;
- all 21 brand candidates whose technical evidence materially improved;
- no fonts.

Seven existing brand ReviewCandidate IDs and workflow states were preserved. The import
created 44 tasks, moving the review queue from 46 to 90. Its second apply created zero
and reported all 51 selected entries unchanged.

The browser now shows dataset/schema, source-version history, manifest membership,
technical readiness, five separate evidence dimensions, review eligibility, governance
ineligibility reasons, and denied operational permissions. It adds no approval,
permission, retrieval, recommendation, or generation controls.

## Authority and exclusions

Final local counts are:

- DecisionEvents: 0;
- HumanAssertionProjection rows: 0;
- GovernanceDecisionProjection rows: 0;
- ALLOWED OperationalPermissionProjection rows: 0;
- provisioned reviewers: 0;
- persistent local signing keys added: 0.

No real approval, governance decision, permission, retrieval, semantic search,
recommendation, automatic selection, design generation, source-binary serving, or legacy
cutover was introduced.

## Finding before DIP-1B-5B

The bounded historical source set did not contain a sufficiently identified hair-care
production design that could be added without inventing a product-family conclusion.
The expansion therefore covers makeup, complexion/skincare-adjacent primer, lip, eye,
concealer, packaging, typography/layout, and minimal/decorative language, while the
hair-care historical-memory gap remains explicit for later source identification.

All 53 new vector assets also remain rights-unreviewed. DIP-1B-5B must not convert review
value or technical readiness into reuse permission.

## Verification

- deterministic evidence and DIP-1B-5A focused tests: green, including byte identity,
  semantic mutation, dry-run no-write behavior, partial failure/retry, source-version
  preservation, identity stability, separate readiness dimensions, bounded review
  idempotency, and browser rendering;
- intelligence suite: 122 passed;
- accounts suite: 258 passed;
- full CI-equivalent Django suite: 916 passed, 1 skipped, 1 documented Pacdora test
  deselected;
- frozen DIP-0/DIP-0B/DIP-0C tooling: 1,014 passed;
- ruff: clean;
- migration drift: none;
- Django deploy check: no error (one expected local weak-SECRET_KEY warning when the
  checked shell uses the development placeholder);
- deterministic successor, expansion manifest, and review manifest regenerated with
  byte-identical output;
- frozen milestone trees, MVP/C3 manifests, stale C3a output, and `materials/` remained
  byte-clean.
