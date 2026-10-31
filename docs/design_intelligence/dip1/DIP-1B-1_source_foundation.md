# DIP-1B-1 — source persistence contracts and default-deny gateway

Status: implementation complete; pending review.

## Boundary

`apps.intelligence` adds stable corpus identity, content-addressed/versioned sources, exact
evidence links, provenance observations, import reconciliation history, and a rebuildable
operational-permission projection. Accounts remains the only identity, authorization,
DecisionEvent, attestation, and protected-decision authority. No mutable approval,
canonical, ownership, licensing, retrieval, or automatic-use flag exists on source or
corpus identity models.

Implemented models are `CorpusItem`, `SourceArtifact`, `EvidenceReference`,
`ProvenanceRecord`, `ImportBatch`, `ImportRecord`, and
`OperationalPermissionProjection`. No historical-design, design-unit, asset, font, brand,
review-candidate, or UI model is included.

## Source and import semantics

SHA-256, not path, is technical content identity. Re-observing one logical source with the
same hash is idempotent even if its path changed. A changed hash appends a new
`SourceArtifact` linked through `supersedes_source_artifact`; evidence continues to point
to the exact prior version. Provenance stores raw observations separately from normalized
machine interpretations and never grants rights.

`ImportBatch` records one attempt and bounded counts. `ImportRecord` is unique per
batch/stable key; identical retries return the same record, identical records in later
batches reconcile as `UNCHANGED`, and changed hashes append `NEW_VERSION` records linked to
the prior successful record. Failures never overwrite prior success. No actual DIP-0 record
is imported and import helpers create neither DecisionEvents nor permissions.

## Default deny

`evaluate_operational_permission` denies missing items, malformed scope, unknown permission,
absent projections, every non-ALLOWED state, expiry, unsupported projection versions,
missing/mismatched signed events, invalid chains, and stale/unavailable signed chain heads.
An ALLOWED row alone has no authority: its signed accounts event must be a permission-grant
action whose payload binds the same item, permission and scope, and the projection must name
the current verified chain head. `AUTOMATIC_USE` additionally requires an independently
verified `RETRIEVAL` projection. Absence always means DENIED; no ALLOWED row is seeded.

The projection table is not registered in admin. Neither hashes nor reconciliation or
provenance history have unrestricted admin write paths.

## Legacy signals

`legacy_signals.characterize_legacy_signals` reads active DesignReferences, legacy approved
images/final outputs, canonical color/aesthetic status, approved material status, and
`BRAND_LOGO_PATH` presence for diagnostics. Every result carries
`LEGACY_SIGNAL_NON_AUTHORITATIVE`; the adapter writes nothing and cannot construct a
projection or decision.

The new intelligence boundary denies by default. Legacy paths remain operational outside
it; repository-wide cutover has not occurred and no claim of repository-wide containment
is made. A later bridge slice must redirect consumers explicitly.

## Migration and exclusions

`intelligence/0001_source_foundation` is additive, depends on `accounts.0005`, seeds no
data, alters no legacy table, and uses UUID primary keys, protected history links, SHA-256
checks, confidence/time/count checks, stable-key uniqueness, and query-specific indexes.
Before real intelligence decisions depend on these tables it is safe to migrate forward,
roll back, and reapply; signed decisions later require forward repair instead of destructive
rollback.

Explicitly excluded: DIP-0 corpus import, observed-fact/classification models, review UI,
semantic/vector retrieval, ranking, recommendations, generation consumers, automatic use,
full projector, and legacy pipeline redirection.

## DIP-1B-2 visibility

DIP-1B-2 may add the smallest domain records and read-only corpus browser on top of these
identities and evidence links. Candidate browser access must remain separate from operational
search permission, and every operational consumer must continue through the default-deny
gateway.
