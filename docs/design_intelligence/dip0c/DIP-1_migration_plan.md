# DIP-1 — migration plan

**Idempotent and reversible before activation. Nothing is executed in DIP-0C5.**

## Steps

1. **Freeze the DIP-0 audit artifacts.** Tag the commit. Milestone records describe what
   was true then and are **never regenerated** under a newer schema.
2. **Import the source-file inventory** (7,586 files) — paths, hashes, categories.
3. **Import technical observations** — DIP-0B design units, C1/C2 readiness, C3 brand and
   palette audits, C4 faces/families/packages.
4. **Import machine recommendations** into a field that **cannot** be read as a decision.
5. **DO NOT import synthetic `TEST_ONLY` decisions.** Every one lives in
   `examples_TEST_ONLY/` and is excluded by path. A fabricated approval in a production
   database is indistinguishable from a real one — that is the whole reason the real ledger
   was kept empty for eleven slices.
6. **Import only real, reviewed human decisions.** There are currently **zero**.
7. **Preserve audit provenance**: parser versions, config versions, taxonomy version, and
   the originating **commit hash** on every imported record.
8. **Reconcile counts before activation.** 7,586 files · 3,966 faces · 2,832 families ·
   1,880 provenance-rights groups · 6,089 review items. A mismatch halts the migration.
9. **Keep every permission `false` after import.** Migration imports *findings*, never
   *grants*.
10. **Activate retrieval only through explicit reviewed decisions** — per record, by an
    authenticated human, through the permission-grant path.

## Idempotence and reversibility

- Every record keys on a **content-derived** identity (SHA-256, face_id, review_item_id),
  so a re-run **updates in place** and never duplicates.
- The migration is **reversible until activation**: nothing is granted, so nothing must be
  revoked. Once a permission is granted, reversal is a **revocation event**, not a rollback
  — the ledger is append-only, and that does not change.

## The reconciliation gate

Migration may not complete unless the imported counts **equal** the frozen DIP-0
reconciliations. Where a milestone has no machine-readable reconciliation (DIP-0B, C1, C2),
its markdown summary is the authority and the discrepancy is **reported, not resolved by
overwriting**.
