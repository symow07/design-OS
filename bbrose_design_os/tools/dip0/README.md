# DIP-0A — `materials/` master inventory

Recursive, read-only audit of the Design Intelligence source library.

```bash
# from the repo root
bbrose_design_os/venv/bin/python -m tools.dip0.run                 # sampled hash verify
bbrose_design_os/venv/bin/python -m tools.dip0.run --full-hash-verify
bbrose_design_os/venv/bin/python -m tools.dip0.run --no-cache      # ignore hash cache

bbrose_design_os/venv/bin/python -m pytest tools/dip0/tests -q     # 94 tests
```

Exit code is non-zero if the source tree changed, a hash drifted, or the output
root resolved inside `materials/`.

## Invariants

- `materials/` is **read-only**. Nothing is renamed, moved, converted,
  deduplicated, optimised or deleted — including junk files.
  - *Annotated 2026-10-04 (the clean-up; the bullet above stands for this audit tool): on the owner's answers Q5 and Q6 to the clean-up list (2026-10-03) and his DL line (2026-10-04), 2318 files (16.24 GB) were MOVED, not deleted, from `materials/` to `~/BBROSE_REMOVED_2026-10-04/materials/` (groups M1-M6 and DL, listed in that folder's MANIFEST.tsv). The inventory, the tier record and the captions lost exactly those files' rows: nothing was re-walked, re-derived or admitted, and `reports/` stay as dated history.*
- Every write goes through `config.assert_output_safe()`, which refuses any path
  under the source root. Outputs land in `var/design_intelligence/audits/dip0/`.
- A pre/post snapshot (size, mtime_ns, inode of every file, junk included) plus a
  hash re-verification prove the above on each run.
- Symlinks are recorded, flagged if they escape the root, and never followed.
- Archives are inventoried by **central-directory manifest only** — never
  extracted, never recursed into.
- Fonts are inspected for metadata only — never installed, embedded or exposed.
  `fsType` bits and bundled licence text are **evidence**, never a rights grant.
- Duplicates are **detected and reported only**.

## Provenance

Every machine-inferred value is an `Inferred` envelope — `value`, `source`,
`evidence[]`, `confidence`, `extracted_at`, `parser`. Human curation lives in a
separate `human_confirmed` block that machine code never writes.

`category` vs `human_confirmed.category`; `license_status` never leaves
`UNVERIFIED` / `PENDING_HUMAN_CONFIRMATION` without a person.

## Taxonomy

User-approved categories, plus `OUT_OF_SCOPE` ("understood, deliberately
excluded") kept strictly distinct from `UNKNOWN` ("cannot yet classify").

Two additions are **proposed, pending DIP-0D sign-off**: `ARCHIVE` and
`LICENSE_EVIDENCE`. Both name things we understand, so filing them under
`UNKNOWN` would dilute it.

## Modules

| Module | Slice | Role |
|---|---|---|
| `config.py` | — | roots, exclusions, extension policy, taxonomy, write guard |
| `provenance.py` | — | `Inferred` envelope + `human_confirmed` block |
| `walk.py` | 1 | symlink-safe walk, streaming SHA-256, resumable cache, duplicate grouping |
| `integrity.py` | 1 | pre/post snapshot, hash re-verification, output-location proof |
| `detect.py` | 2 | magic-byte signature, MIME, `.ai` parser routing (PDF vs legacy PostScript) |
| `archives.py` | 2 | zip manifests, encrypted/corrupt/empty/nested/traversal/bomb flags |
| `fonts.py` | 2 | fontTools inventory metadata, quarantine posture |
| `classify.py` | 3 | ordered rule table, licence evidence, ownership, review flags |
| `pilot.py` | 4 | representative subset selection + requirements proof |
| `report.py` | 4 | inventory JSONL/CSV, reports, reconciliation, divergence |
| `run.py` | 5 | orchestrator |

## Outputs

```
var/design_intelligence/audits/dip0/
  inventory/   inventory.jsonl · inventory.csv · symlinks.json · excluded_junk.json
  reports/     summary.md · duplicates.json · archives.json · fonts.json
               reconciliation.json · divergence.json
  manifests/   pilot_manifest.json
  temporary/   hash_cache.json
```

Every record preserves its `materials/...` relative path, so it traces back to
its source file. `divergence.json` compares each run to the pre-audit estimates
rather than silently absorbing drift.
