# DIP-1B-5A evidence reconciliation

## Append-only import

The deterministic successor was imported as a new JSON `SourceArtifact` in batch
`7dd400c2-3f59-4024-8d3a-2db91ba1aed1`.

The import created:

- one new SourceArtifact and one SourceLocationObservation;
- one source-declaration ImportRecord;
- 21 candidate evidence ImportRecords;
- 21 `DETERMINISTIC_BRAND_EVIDENCE_RECORD` EvidenceReferences;
- bounded technical-readiness ObservedFacts and provenance records.

All previous SourceArtifacts, EvidenceReferences, ImportBatches, ImportRecords, and
stored hashes remain present. Each new evidence record is linked to the same existing
`brand:dip0c3-brand:00` through `brand:dip0c3-brand:20` CorpusItem. No brand candidate
or ReviewCandidate identity was duplicated.

The unchanged-input second apply returned the existing completed batch, created no
row, and reported all 21 semantic records unchanged.

## Integrity results

All 21 affected candidates have the same dimensional result:

| Dimension | Result | Reason |
| --- | --- | --- |
| Overall | `PARTIALLY_VERIFIED` | The deterministic technical record verifies while the historical stale evidence remains preserved and unresolved. |
| `TECHNICAL_EVIDENCE_READY` | true | The selected canonical JSON record and SourceArtifact content identity verify. |
| `BRAND_IDENTITY_EVIDENCE_READY` | false | No authoritative brand-identity evidence was imported. |
| `RIGHTS_EVIDENCE_READY` | false | No ownership or licence evidence was imported. |
| `PALETTE_AUTHORITY_EVIDENCE_READY` | false | A technical color parse cannot establish an official palette. |
| `GOVERNANCE_READY` | false | Composite identity/rights or palette/rights requirements are incomplete. |

The canonical resolver evaluates selected evidence. Selecting the new deterministic
record alone can support bounded technical or brand review. Selecting an affected old
physical/C3a source continues to surface the historical integrity policy. Composite
governance attestations remain fail-closed because technical evidence alone cannot
satisfy technical-and-brand, color-and-brand, ownership, or rights categories.

No evidence-sufficient assertion, governance attestation, final decision, reviewer,
or signing key was created.

## Authority reconciliation

After import and after the idempotent repeat:

- DecisionEvents: 0;
- HumanAssertionProjection rows: 0;
- GovernanceDecisionProjection rows: 0;
- ALLOWED OperationalPermissionProjection rows: 0.
