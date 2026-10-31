# DIP-1B-4A — Deterministic Human Assertion Projections

Status: implemented; awaiting review before DIP-1B-4B.

## Boundary

DIP-1B-4A replaces browser event scanning with a deterministic, rebuildable,
atomically published human-intelligence read model. It does not approve ownership,
licence, canonical identity, palettes, or business scope and does not grant retrieval,
automatic use, export, production use, recommendation, generation, or legacy cutover.
`ReviewCandidate` remains workflow coordination, `MachineClassification` remains
non-authoritative machine output, and `OperationalPermissionProjection` remains the
separate fail-closed permission layer.

The accepted DIP-1B-3 commit is
`f01c46a953177a7e5878a2e35f6357b25582de7c`.

## Additive schema

`intelligence/0004_human_assertion_projections.py` creates only:

- `IntelligenceProjectionGeneration`, which records a complete attempted build,
  immutable version/checkpoint/count/output metadata, safe failure codes, and the
  `BUILDING`, `VALIDATED`, `PUBLISHED`, `FAILED`, and `SUPERSEDED` lifecycle;
- `HumanAssertionProjection`, an immutable derived row unique by generation,
  CorpusItem, and assertion domain, with its exact source event/sequence,
  reviewer/role, frozen policy, evidence metadata, warnings, and effective time;
- `ProjectionPublicationState`, a constrained singleton pointing to the current
  generation and its chain checkpoint.

The migration has no data operation. Forward, rollback, and reapplication preserve
existing corpus, asset profiles, ReviewCandidates, DecisionEvents, and permissions and
seed no assertion, reviewer, or ALLOWED permission state. Directly created projection
rows have no authority because readers accept rows only through the verified publication
singleton.

## Projector contract

The projector identifier is `bbrose.intelligence.human_assertion_projector`, projector
version `1.0`, and projection schema `human_assertion_projection/1.0`. The only supported
signed actions are:

- `record_intelligence_classification`;
- `correct_intelligence_classification`;
- `record_intelligence_evidence_assessment`;
- `request_intelligence_clarification`.

Before reducing anything, the projector verifies the complete event chain and signed
head. Each supported event is then checked against the pinned DecisionEvent and assertion
schemas, cryptographic signature/content hash, signed authorization snapshot, frozen
policy and selected role, canonical CorpusItem and ReviewCandidate/domain binding,
evidence ownership and source hashes, and signed supersession reference. Unsupported
intelligence actions, event/assertion schemas, or policy versions fail closed. Failures
store bounded error codes only—never secrets or full payloads.

## Deterministic reduction

Rows are derived from signed event sequence, frozen policy versions, immutable identity
resolution, explicit projector/schema versions, and an explicit evaluation time (or the
terminal event time; genesis uses the UTC Unix epoch). The reducer does not consult
current reviewer assignments, ReviewCandidate status, current machine output, legacy
approval fields, permissions, wall-clock time, or database primary-key order.

Corpus/domain keys, evidence IDs and source rows, warnings, supersession processing, and
output rows are canonically ordered. The logical output hash binds the projector,
projector version, schema version, and canonical row document. Rebuilding the same chain
with the same evaluation time produces byte-equivalent logical rows and the same hash.

A correction applies only to an earlier supported classification on the same canonical
CorpusItem and domain. Valid signed correction makes exactly one assertion effective;
prior events and prior generations remain queryable. Cross-item/domain, missing, forward,
cyclic, or incompatible supersession fails closed. Multiple active assertions without a
valid supersession project `REVIEW_REQUIRED`; the reducer never chooses an arbitrary
winner.

Evidence assessment is a separate `evidence_assessment` domain. Sufficient,
insufficient, and clarification-required states do not replace classification history and
never turn a classification into approval or permission.

## Shadow generation and atomic publication

Apply mode creates `BUILDING`, verifies and reduces without a long-held chain lock,
persists the unpublished rows, validates counts and invariants, and marks `VALIDATED`.
A short transaction then locks the current chain head and publication singleton,
reconfirms the expected checkpoint, marks the former published generation
`SUPERSEDED`, advances the singleton, and marks the new generation `PUBLISHED`. Any
failure rolls the transaction back and leaves the former pointer current while the new
generation becomes `FAILED`. Unpublished or failed rows are never read as current.

The command `rebuild_intelligence_assertions` is write-free by default; `--apply` is
required to persist. It supports text or `--json`, an aware
`--evaluation-timestamp`, and `--expected-chain-head` (lowercase SHA-256 or `GENESIS`).
Fatal verification/validation returns non-zero. Repeated apply on an unchanged checkpoint
and evaluation time is idempotent.

## Staleness and browser behavior

The list, corpus detail, and review detail pages consume only the published projection.
They expose `CURRENT`, `STALE`, `NOT_BUILT`, `REVIEW_REQUIRED`, or `INVALID`, and show the
generation UUID, exact source head/terminal sequence, warning codes, source DecisionEvent,
classification, independent evidence assessment, and immutable signed history. Machine
classification, human projection, projection status, and operational permission have
separate labels. A newly appended event makes the old checkpoint `STALE`; stale rows are
not presented as current and cannot drive the correction form. Reads write no projection,
event, workflow, or permission data.

## Local bounded application

The approved local database began with 117 CorpusItems, 47 DesignAssetProfiles, 46
ReviewCandidates, and zero DecisionEvents, ReviewerProfiles, role assignments, or ALLOWED
permissions. No signing key or real reviewer was configured.

- Migration `intelligence.0004_human_assertion_projections` applied cleanly.
- Two pre-apply dry runs were identical and write-free: genesis sequence 0, 0 events,
  0 rows, 0 warnings, output hash
  `e369f5e504b86c7810fd0bf38d41bb0608f08a8d638f254760d14fb32b961ca1`.
- Apply published generation `0dbfb64a-b556-4117-912d-54b922272ff4` with 0 rows.
- The second apply returned idempotent and created no generation or row.
- Final local state: 1 PUBLISHED generation, 0 HumanAssertionProjection rows,
  0 DecisionEvents, 0 ALLOWED permissions, 0 ReviewerProfiles, and 0 role assignments.

## Verification and frozen state

- focused projection/migration/browser/review regression: 36 passed;
- complete application regression in canonical test mode, excluding the baseline item
  below: 864 passed, 1 skipped, 2 deselected;
- frozen DIP tool regression, including committed-artifact guards: 670 passed;
- scoped Ruff, Python compilation, migration drift detection, Django model checks, and
  whitespace checks: clean;
- committed `docs/design_intelligence`, `materials`, and frozen DIP artifacts were not
  modified by this slice.

One pre-existing local audit-output discrepancy requires reconciliation before relying on
the production-manifest integration test in DIP-1B-4B:
`var/design_intelligence/audits/dip0c/c3a/brand_candidates.json` is ignored, was last
modified before the approved DIP-1B-3 commit, and currently hashes to `5873424819b4776796df7b083636bbe19b5af24f74265c6c36a12d60202434f7`, while the frozen
manifest pins `dfccbad26e98744e78d606fec85a301a9d3d2357ff17cf8ece5fcbe7a2d9e62b`.
This slice did not rewrite either the ignored output or the manifest.

Stop for review before DIP-1B-4B.
