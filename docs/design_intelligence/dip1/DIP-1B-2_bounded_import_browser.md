# DIP-1B-2 — Bounded DIP-0 import and read-only corpus browser

Status: implemented; held for review before DIP-1B-3.

Foundation: DIP-1B-1 commit `66644fa`.

## Corrected candidate-dataset wording

Import the DIP-0C2 candidate pilot: **20 manifest entries covering 19 unique
sources and producing 48 frozen AssetCandidate records that resolve to 47
semantic candidates.** Preserve DIP-0C1 separately as the earlier **24-entry
source-audit pilot**.

The earlier wording that described a 24-source pilot producing 48 candidates
conflated two frozen datasets. This clarification does not rewrite either one:

- `dip0c1_reusable_source_audit/1.0` is frozen technical source-audit evidence,
  not the authoritative candidate list. Its 10 C2-overlap lineages are recorded
  separately in this import; its C1-only sources remain outside this scope.
- `dip0c2_asset_candidate_pilot/1.0` is the authoritative source for 48 frozen
  AssetCandidate records resolving to 47 semantic DesignAsset candidates.

The 19 C2 logical sources contain 18 SHA-256 content identities because the two
`5955564.eps` locations are an exact duplicate pair. A mandatory pre-1B-3 check
compared both complete C2 records and resolved them as **Case A: one semantic
whole-file candidate with two origin/evidence records**. Both records, locators,
ImportRecords, and provenance lineages remain preserved; they now share one
CorpusItem and one DesignAssetProfile. See
`DIP-1B-2_asset_identity_clarification.md`.

Each imported C1 overlap lineage points to the exact matching record in the
committed, frozen 24-entry `docs/design_intelligence/dip0c/pilot_manifest.json`.
The regenerable per-file C1 audit JSON under ignored `var/` is not a manifest
dependency. The two repeated C1 pilot roles resolve to the final corresponding
record for their physical source; this bounded import still records 10 shared
sources and does not imply that any C1-only source was rejected.

## Manifest and safety boundary

The versioned manifest is
`docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json`, schema and manifest
identifier `dip1b_mvp_manifest/1.0`.

It names exact configured-root-relative paths, SHA-256 values, dataset ids,
source schemas, parser/importer identities, stable keys, record types, bounded
JSON locators, and non-test state. It does not scan `materials/`.

Before any write, validation rejects:

- an unknown manifest, importer, dataset, source, or locator schema;
- absolute paths, traversal, root escape, or a path outside configured prefixes;
- hash mismatch or unavailable source evidence;
- test-only, test-ledger, or synthetic-approval sources;
- conflicting stable keys or conflicting candidate content within one source;
- any deviation from 20 C2 entries, 19 C2 logical sources, 18 content
  identities, 48 frozen C2 candidate records, or 47 semantic candidates;
- any deviation from the other bounded corpus counts.

The command is dry-run by default:

```text
python manage.py import_dip0_mvp \
  --manifest ../docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json
```

Persistence requires the explicit `--apply` flag. Validation and dry-run do not
create an ImportBatch or any other database row.

## Additive persistence

Migration `intelligence/0002_corpus_browser_foundation.py` creates only:

- `SourceLocationObservation`
- `ObservedFact`
- `MachineClassification`
- `HistoricalDesignProfile`
- `DesignUnit`
- `DesignAssetProfile`
- `FontFaceProfile`
- `BrandCandidateProfile`

Source-location observations are append-only logical locations. SHA-256 remains
the content identity, so relocation and exact duplicate bytes share a
SourceArtifact while retaining every observed location. Audit conclusions and
candidate provenance do not transfer through shared bytes.

Observed facts remain separate from machine classifications. Candidate profiles
contain no human-approval, ownership, licence, retrieval, or automatic-use
field. Historical designs are constrained to `REFERENCE_MEMORY_ONLY`; their
layouts, dielines, and artwork are not reusable templates.

The imported C2 asset profile uses dataset identifier plus frozen candidate key
as its semantic identity. Its canonical source-manifest field is deterministic;
every origin remains independently represented by its exact SourceArtifact,
`json_path/1.0` EvidenceReference, ProvenanceRecord, and ImportRecord.

Explicit bounded locator schemas are:

- `json_path/1.0`
- `jsonl_record/1.0`
- `file_page/1.0`
- `illustrator_artboard/1.0`
- `archive_member/1.0`
- `font_face/1.0`
- `source_file/1.0`

They accept data only, enforce allowed keys/types/lengths/numeric bounds, and
reject traversal and executable expressions.

## Development-database application

The configured database was verified before mutation as PostgreSQL `bbrose_db`
on loopback `::1`, using the local placeholder database user. Before migration
it contained 3 auth users, 35 sessions, 44 migration rows, no DecisionEvent
table, and no intelligence tables.

Applied migrations:

- accounts through `0005_bootstrapstate`;
- intelligence through `0002_corpus_browser_foundation`.

The pre-import chain was a genesis head: terminal sequence 0, event count 0,
terminal hash null, and zero DecisionEvents. Users and sessions remained 3 and
35.

The identity-clarified manifest dry run returns hash
`7dbb22815265c0dc790e74003840fb861299beddd020179094f36129f86186aa`
and the same exact reconciliation. Initial applied batch
`f1f9b8a3-8b33-4f90-8357-b2b7fac49e05` completed with 391 created ImportRecords,
zero failures, and no skipped or quarantined records. The frozen-artifact guard
then exposed that the first scaffold had pointed its C1 overlap locators at
regenerable ignored audit JSON. After correcting those locators to the frozen C1
pilot manifest and refreshing the bounded brand-audit hash, reconciliation batch
`12a0736c-020c-46d6-b0e8-674c6789bd6d` completed with 46 `NEW_VERSION` and 345
`UNCHANGED` ImportRecords, zero failures, and no changed corpus counts. Earlier
lineage remains queryable.

Controlled identity-correction batch
`c910a781-8407-4842-aa17-c3d7a633f4fb` then normalized all 47 semantic external
keys and merged the one duplicate subject. It appended one audit ImportRecord,
deleted no evidence, fact, classification, provenance, or prior ImportRecord,
and created a permanent browser redirect for the legacy UUID. The development
database now has 3 completed batches and 783 ImportRecords.

Post-import state:

| Record | Count |
|---|---:|
| CorpusItem | 117 |
| HistoricalDesignProfile | 14 |
| DesignUnit | 173 |
| frozen C2 AssetCandidate records | 48 |
| DesignAssetProfile (semantic candidates) | 47 |
| distinct C2 candidate keys | 47 |
| C2 logical origins represented by evidence | 19 |
| C2 content artifacts represented by asset profiles | 18 |
| FontFaceProfile | 34 |
| brand candidates | 21 |
| palette candidates | 1 |
| C1 overlap provenance lineages | 10 |
| ObservedFact | 291 |
| MachineClassification | 277 |
| EvidenceReference | 291 |
| DecisionEvent | 0 |
| ALLOWED OperationalPermissionProjection | 0 |

The decision-chain head remains at genesis sequence 0. The database still has
the original 3 users and 35 sessions, with no reviewer profile or role seeded.
The final post-import dry run reproduced the same manifest hash and counts, so
the import itself changed no source file.

Record-level re-import idempotency and changed-record versioning are exercised
against PostgreSQL tests. Identical records reconcile as `UNCHANGED`; changed
records append `NEW_VERSION` ImportRecords with protected prior links. Per-record
transactions preserve earlier successes if a later bounded record fails.

## Read-only candidate browser

Routes:

- `/intelligence/corpus/` — bounded corpus list, filters, and search;
- `/intelligence/corpus/<corpus-item-uuid>/` — candidate detail.

The server uses the existing canonical accounts action `review_evidence`. It is
appropriate without changing the pinned authorization policy and authorizes
active, enabled `LEGAL_REVIEWER`, `BRAND_ADMIN`, and `DESIGN_REVIEWER` role
holders. Unauthenticated, inactive, reviewer-disabled, and other-role users are
denied server-side. Every access is authorization-audited.

Candidate-browser authorization is independent of operational permission. It
does not require `VISIBLE_IN_REVIEWER_SEARCH` or `RETRIEVAL`, and it appends no
DecisionEvent.

The browser provides item-kind, source, import-batch, technical-readiness,
candidate-type, and bounded stable-key/display-label filters. Detail pages show:

- source hashes and bounded evidence locators;
- provenance and dataset lineage;
- observed technical facts;
- machine classifications and confidence;
- historical design units;
- font, brand, and palette candidate warnings;
- `HUMAN DECISION: NONE` when no signed state exists;
- fail-closed operational-permission results;
- `LEGACY SIGNAL: LEGACY_SIGNAL_NON_AUTHORITATIVE`.

No absolute source path is rendered. Binary preview/download is deferred because
there is no existing root-restricted source-serving mechanism suitable for this
corpus.

## Explicit non-capabilities

This slice introduces no semantic/vector search, similarity ranking,
recommendation, generation, automatic asset/font selection, source-file serving,
approval/correction form, signed intelligence decision, permission grant,
operational retrieval, projector, or legacy-pipeline cutover.

The local database has no reviewer profiles or role assignments seeded by this
slice. An existing user becomes able to open the browser only through the
separately controlled reviewer-role lifecycle; candidate import must never grant
review authority as a side effect.

## Verification

- application regression: 831 passed, 1 skipped, 1 intentionally deselected;
- frozen DIP-0/DIP-0B/DIP-0C tools: 1,013 passed;
- focused intelligence regression after identity clarification: 38 passed;
- scoped Ruff checks, migration-drift check, and `git diff --check`: clean;
- frozen committed DIP artifacts and `materials/`: clean in Git before and after;
- path-root, hash, test-only, dry-run, idempotency, partial-failure, migration,
  authority, and browser guards are covered by the focused tests.

Stop for review before DIP-1B-3.
