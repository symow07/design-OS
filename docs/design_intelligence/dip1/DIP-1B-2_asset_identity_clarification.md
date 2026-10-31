# DIP-1B-2 follow-up — C2 AssetCandidate identity clarification

Status: implemented as the mandatory pre-1B-3 identity check. DIP-1B-3 has not
started.

## Decision: Case A

The two frozen C2 records carrying candidate key `b6bea969da5892a6` represent
**one semantic candidate with two origin/evidence records**.

| Evidence | Origin 1 | Origin 2 |
|---|---|---|
| manifest key | `dip0c2-asset-source:15` | `dip0c2-asset-source:17` |
| logical source | `DOWNLOADS 12-2025/5955564.eps` | `flat-black-friday-stickers-collection/5955564.eps` |
| pilot role | `cross_format_family_eps` | `exact_duplicate_sibling` |
| source SHA-256 | `6ecf3b0c…40f3` | `6ecf3b0c…40f3` |
| record locator | source-specific C2b JSON, `candidates[0]` | source-specific C2b JSON, `candidates[0]` |
| candidate boundary | whole file, page/artboard null | whole file, page/artboard null |
| segmentation | `NONE` / `UNAVAILABLE` | `NONE` / `UNAVAILABLE` |
| bounds | 0, 0, 500, 500 pt | 0, 0, 500, 500 pt |
| candidate category | `UNKNOWN_ASSET_TYPE` | `UNKNOWN_ASSET_TYPE` |
| parser/configuration | identical | identical |
| technical metadata | identical | identical |

The acquisition contexts retain different earlier inventory labels
(`REUSABLE_VECTOR_ASSET` and `MOTIF`). Those labels and logical paths are
lineage evidence, not different extraction coordinates, members, or intended
candidate boundaries.

C2's frozen candidate-key algorithm is also explicit: source bytes,
segmentation method, rounded candidate bounds, configuration fingerprint, and
candidate index feed the key. The conclusion therefore does not rest on the
content hash alone. The complete records agree on every semantic boundary field,
and one C2 manifest entry explicitly identifies itself as the exact-duplicate
sibling.

## Identity contract

- Frozen candidate-record count: **48**.
- Semantic candidate count: **47**.
- C2 physical SourceArtifact count: **18**.
- Semantic external key:
  `asset:dip0c2_asset_candidate_pilot/1.0:<frozen-candidate-key>`.
- The canonical source-manifest key is the lexically first frozen origin key;
  record order never selects it.
- A repeated key is accepted as one semantic candidate only when the complete
  records match after removing acquisition-only path and prior-inventory context.
  A different boundary under the same key fails manifest validation.
- Future decision-subject resolution requires exactly one matching profile and
  fails closed on zero or multiple subjects.

No numeric or import-order suffix is generated.

## Persistence and lineage

One CorpusItem and one DesignAssetProfile now represent the shared candidate.
Both frozen origin records retain separate:

- bounded JSON EvidenceReferences;
- ProvenanceRecords;
- source-location observations;
- origin-scoped ObservedFacts and MachineClassifications;
- ImportRecords across every import batch.

The importer reports `asset_candidates: 48`,
`semantic_asset_candidates: 47`, and `c2_content_identities: 18` independently.

## Controlled local correction

No migration was required. The command is dry-run by default:

```text
python manage.py reconcile_dip1b2_asset_identity \
  --manifest ../docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json
```

Persistence requires `--apply`. It refuses candidate subjects carrying signed
DecisionEvents or permission projections, performs one transaction, and audits
the correction with an ImportBatch and ImportRecord.

Applied batch: `c910a781-8407-4842-aa17-c3d7a633f4fb`.

| Local development state | Before | After |
|---|---:|---:|
| CorpusItem | 118 | 117 |
| DesignAssetProfile | 48 | 47 |
| distinct C2 candidate keys | 47 | 47 |
| C2 asset SourceArtifacts | 18 | 18 |
| EvidenceReference | 291 | 291 |
| ObservedFact | 291 | 291 |
| MachineClassification | 277 | 277 |
| ImportRecord | 782 | 783 |
| DecisionEvent | 0 | 0 |
| ALLOWED permission projections | 0 | 0 |

Canonical CorpusItem UUID:
`fa90d60c-6f58-4f96-9223-4743af3a8234`.

Legacy UUID `5a0a2de8-d65a-4de1-a058-a5e94b883690` is preserved as an immutable
identity-reconciliation provenance alias. Its prior browser URL permanently
redirects to the canonical UUID. The four existing origin ImportRecords, two
evidence locators, and two candidate provenance records all point to the
canonical subject after reconciliation.

A second dry run reports 47 profiles before and after, zero merges, zero key
normalizations, and no batch: the correction is idempotent.

## Verification

Tests prove record-order independence, repeated-import stability, one semantic
subject, preserved duplicate-content lineage, fail-closed future subject
resolution, rejection of a same-key/different-boundary record, absence of silent
suffixing, stable canonical UUID and browser URL, legacy URL redirect, and the
48/47/18 reconciliation.

No DecisionEvent, operational permission, approval, retrieval, recommendation,
generation, or automatic-use capability was introduced.
