# DIP-1B-3 — Human Review Queue and Signed Intelligence Assertions

Status: implemented; awaiting review before DIP-1B-4.

## Boundary

DIP-1B-3 adds authenticated human intelligence review to the bounded corpus. It does not
approve, activate, canonicalize, license, retrieve, recommend, generate, publish, or grant
operational use. The interface states this boundary explicitly:

> HUMAN INTELLIGENCE ASSERTIONS DO NOT AUTHORIZE OPERATIONAL USE.

The accepted DIP-1B-2 identity follow-up is
`cef40f16cb5ce795870b9a30e928415327040206`. The canonical reconciled asset remains
`fa90d60c-6f58-4f96-9223-4743af3a8234`; the former UUID is excluded from the review
manifest and rejected as a DecisionEvent subject.

## Migration and workflow model

`intelligence/0003_review_candidates.py` adds only `ReviewCandidate`, its five bounded
review types, five workflow statuses, assignment/priority constraints, a manifest-scoped
uniqueness constraint, and queue indexes. The migration has no data operation and seeds no
reviewer, DecisionEvent, or permission row.

Workflow state coordinates work only. Claim and release lock the ReviewCandidate row,
derive the actor from the authenticated user, prevent claim stealing, use POST/CSRF in the
browser, and append no DecisionEvent. A `COMPLETED` task is not an approval.

## Review manifest

The frozen declaration is `dip1b_review_manifest/1.0` with SHA-256
`ac8821ca6fc0338b703f1ca4c0dd5371cb6333ca1e31302fb060704ad54318b9`.

| Review type | Tasks |
| --- | ---: |
| Historical memory | 14 |
| Design asset | 14 |
| Font technical | 10 |
| Brand identity / selected logos | 7 |
| Palette observation | 1 |
| Total | 46 |

Every entry pins the CorpusItem UUID and external key. Validation fails on duplicate or
missing identities, deprecated aliases, kind/type mismatches, test-only evidence or
profiles, sources outside configured roots/prefixes, and exact-count drift. The
`import_dip1b_review_tasks` command is dry-run by default and requires `--apply`; repeat
application is idempotent.

## Authorization policy

The current policy is `bbrose.reviewer.authz` version `authz/1.1`. The exact `authz/1.0`
mapping remains registered for signed historical interpretation. Version 1.1 adds:

- `view_intelligence_review_queue`
- `claim_intelligence_review`
- `record_intelligence_classification`
- `correct_intelligence_classification`
- `record_intelligence_evidence_assessment`
- `request_intelligence_clarification`

Domain schemas further restrict which selected role may classify each review type.
`SYSTEM_ADMIN` is excluded from all six actions and cannot make substantive assertions.

## Signed schemas and services

Classification payloads use `intelligence_assertion/1.0`. The strict caller contract
accepts only the canonical CorpusItem UUID, ReviewCandidate UUID, domain, label, normalized
JSON, explanation, EvidenceReference IDs, and MachineClassification IDs. Actor, role,
authorization snapshot, chain fields, hashes, signing key, policy version, event id, and
timestamp are rejected as caller input.

The signed payload records `assertion_schema`, canonical item/candidate identity, domain,
asserted label, normalized value, explanation, evidence IDs, evidence/source hashes,
machine-classification IDs, policy identifier/version, and a server-built authorization
snapshot. Evidence and machine output must belong to the same CorpusItem. The event append
and subsequent workflow update are atomic.

Corrections append `correct_intelligence_classification`, preserve the prior event, and use
the signed supersession field. Only a current record/correction on the same canonical item,
ReviewCandidate, and classification domain is eligible. Cross-item, unrelated, missing,
forward, and already-superseded references fail closed.

Evidence statements use `intelligence_evidence_assessment/1.0` and the bounded values
`EVIDENCE_SUFFICIENT`, `EVIDENCE_INSUFFICIENT`, and `CLARIFICATION_REQUIRED`. The signed
payload declares `authority_effect: NONE`. Insufficient/clarification statements may move
workflow to `NEEDS_INFORMATION`; they do not create authority or permission.

## Temporary read model and UI

`current_intelligence_assertions/1.0` is a temporary, write-free review-display reader. It
verifies the whole DecisionEvent chain first, verifies supported events, checks canonical
subjects and ReviewCandidate/domain bindings, applies signed supersession, and returns one
deterministic current classification per domain plus complete signed history. An invalid or
ambiguous state returns `REVIEW_REQUIRED`; it never repairs data or infers approval.

Routes are rooted at `/intelligence/reviews/` and provide bounded assignment/status/type
filters, detail, POST-only claim/release, classification/correction, evidence assessment,
and clarification controls. Observed facts, machine output, signed human history, and
operational permission are visibly separate. No source-binary route was added.

## Local application result

- Database before: 117 CorpusItems, 47 DesignAssetProfiles, 0 ReviewCandidates,
  0 DecisionEvents, 0 ALLOWED permission projections.
- Migration: `intelligence.0003_review_candidates` applied.
- First and second pre-apply dry runs: 46 would-create, 0 writes, identical hash/counts.
- Apply: 46 created with the exact 14/14/10/7/1 split.
- Post-apply dry run: 0 would-create, 46 unchanged.
- Database after: 117 CorpusItems, 47 DesignAssetProfiles, 46 OPEN/unassigned
  ReviewCandidates, 0 DecisionEvents, 0 ALLOWED permission projections.
- Reviewer provisioning: none; ReviewerProfile and ReviewerRoleAssignment remain zero.

No frozen DIP-0 artifact, audit output, or source file was changed.
