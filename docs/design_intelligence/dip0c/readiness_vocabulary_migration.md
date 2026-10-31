# Technical-readiness vocabulary migration

## The change

```
READY_AFTER_RIGHTS_REVIEW  →  TECHNICALLY_USABLE_WITH_CAVEATS
```

**This was a terminology correction with no logic or result change.**

## Why

DIP holds two axes strictly apart:

- **Axis A — technical readiness:** what the *artefact* is (editable geometry,
  resolution, corruption, tooling limits).
- **Axis B — rights readiness:** ownership, licensing, permissions.

`READY_AFTER_RIGHTS_REVIEW` named the **rights** axis from inside the **technical**
axis. A technical verdict must describe the artefact and nothing else; whether a
rights review is outstanding is already carried by axis B (`ownership: unconfirmed`,
`license: unverified`, all permissions `false`) and by the reuse-posture axis. The
old name therefore leaked axis B into axis A and is retired.

## Canonical vocabulary (all DIP stages: C1, C2a, C2b and future)

```
TECHNICALLY_READY
TECHNICALLY_USABLE_WITH_CAVEATS
NEEDS_CLEANUP
NEEDS_VECTOR_RECONSTRUCTION
REFERENCE_ONLY
QUARANTINE
REJECT_CANDIDATE
```

`TECHNICALLY_READY` = no technical defects. `TECHNICALLY_USABLE_WITH_CAVEATS` =
technically usable with minor, non-blocking caveats. **Neither says anything about
rights.** No value in this vocabulary may refer to ownership, licensing, reuse
posture, retrieval or automatic use.

(DIP-0C2b will extend this same tuple with `REQUIRES_TOOL` and
`HEADER_ONLY_PARTIAL`; it remains one vocabulary, never a parallel one.)

## What did NOT change

Nothing except the name. Explicitly unchanged: classification logic, thresholds,
every readiness outcome other than the renamed value, rights status, ownership
status, retrieval eligibility, automatic-use permissions, production-use
permissions.

**Proof — the C1 pilot before and after are identical:**

| Readiness | Before | After |
|---|---|---|
| `READY_AFTER_RIGHTS_REVIEW` → `TECHNICALLY_USABLE_WITH_CAVEATS` | 14 | **14** |
| `NEEDS_VECTOR_RECONSTRUCTION` | 1 | **1** |
| `NEEDS_CLEANUP` | 2 | **2** |
| `REFERENCE_ONLY` | 4 | **4** |

24 pilot files, 2 classification overrides, 1 JPEG-shell (`5955567.ai`), 0 parser
failures, and identical reuse-posture totals — before and after. Pinned by
`test_migration_preserves_c1_counts_and_classifications`.

## Traceability

The original C1 commit (`d0bf01e`) is **not** rewritten. The migration is a
separate commit on top, so the historical record and the correction are both
visible in `git log`.

## Compatibility guard

- **Emission:** the `READY_AFTER_RIGHTS_REVIEW` constant no longer exists, and
  `config.readiness_value()` raises `ReadinessVocabularyViolation` if the retired
  token is ever passed. `run_c1` additionally fails the run if the token appears
  anywhere in generated output (`no_retired_readiness_vocabulary`) or if a value
  falls outside the canonical tuple (`readiness_vocabulary_canonical`).
- **Reading legacy data:** `config.normalize_readiness(value)` maps the retired
  token forward and reports whether it migrated;
  `config.normalize_readiness_block(block)` normalizes a stored readiness envelope
  and **records the migration in that record's own provenance**
  (`vocabulary_migrated_from`, plus an evidence line), so a normalization is never
  silent.

## Tests

`tools/dip0c/tests/test_readiness_vocabulary.py`:

- the retired constant is gone and the guard refuses the retired/unknown value;
- legacy stored data normalizes forward, with provenance, without mutating input;
- C1 and C2 share one vocabulary (C2's axis A is the same tuple, merely `UNSCORED`
  until C2b scores it);
- readiness never grants rights (rights/retrieval stay false at
  `TECHNICALLY_USABLE_WITH_CAVEATS`);
- **the migration changes no record counts and no classifications.**
