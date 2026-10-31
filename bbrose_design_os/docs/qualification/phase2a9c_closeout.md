# Phase 2A-9C — Multi-Archetype Qualification Framework — CLOSEOUT

Date: 2026-07-23. Framework schema: capability-driven qualification
(`apps/dielines/qualification/`). Four slices, each committed and reviewed:
0 framework, 1 STE, 2 Skynte, 3 RTE.

## Framework (slice 0, `19fd13d`)

Archetype-agnostic (§11): each archetype supplies a `ClosureModel`
(`closure.py`), a parameter contract (`contract.py`), a derived domain, a
collision report and an in-domain sampler; the runner, invariants, folded
simulator and `qualify_dimensions` endpoint read those declarations.
Qualifying one archetype never validates another. Authority states
(`authority.py`) are four independent records — only
`TECHNICALLY_QUALIFIED_DOMAIN` is machine-grantable; the two `PHYSICALLY_*`
states require recorded FIT_PASS evidence; `PRODUCTION_AUTHORIZED_BY_
MANUFACTURER` is never machine-granted. The opposing-tuck baseline (2A-9B)
reproduces byte-identically through the generalized code (pinned by
`test_qualification_framework`).

## Qualified archetypes

| Archetype / version | authority | domain headline | defect? | version decision |
|---|---|---|---|---|
| reference_opposed_tuck_carton/0.1 | TECHNICALLY_QUALIFIED_DOMAIN | W ≥ D+t+20, t ≤ 1.0 | none | 0.1 (2A-9B) |
| straight_tuck_end_carton/1.1 | TECHNICALLY_QUALIFIED_DOMAIN (narrow) | 1.262·D ≤ W < (D+H/2)/1.227 | **YES ×2** | 1.1 kept; **1.2 proposed** |
| skynte_foundation_tuck_carton/1.0 | TECHNICALLY_QUALIFIED_DOMAIN | W ≥ 1.262·D, W < 73.4 | none | 1.0 (no bump) |
| reverse_tuck_end_carton/1.1 | TECHNICALLY_QUALIFIED_DOMAIN (narrow, **provisional**) | same band as STE | shares STE's ×2 | 1.1 kept; 1.2 would follow STE 1.2 |

Deterministic sweep seeds: opposed 20260722, STE 20260723, Skynte 20260724,
RTE 20260725. Each sweep = 150 in-domain + 250 whole-space samples,
**0 failures / 0 crashes** across all four. Every archetype has its own
committed reports under `docs/qualification/<template>_<version>/`
(parameter schema, supported domain, qualification matrix, property-test
report, investigation/versioning, physical-test matrix, folded renders).

## Cross-archetype finding

The DECISION-016 **W-derived tuck** (`W × 1.227`, measured from a square
28×28×120 reference that hid the W/D distinction) is the single root defect
shared by STE 1.1 and RTE 1.1: it makes the tuck lip exceed H/2 on
wide-short cartons and confines both to a narrow domain. **Skynte 1.0
already uses the correct D-derived closure** (tuck = D + lip, DECISION-019)
and is defect-free — it is the validated model the STE/RTE 1.2 correction
would adopt.

## Non-regression (§10)

- task #50 (opposed-tuck) geometry, hash `0f5b8bf6…`, physical-test
  approval and authority states: **unchanged**
- task #47 (Skynte) golden reference `2be58c7b…`: **unchanged**, generator
  reproduces it byte-identically
- opposed-tuck 2A-9B committed reports + byte-stability: **unchanged**
- STE 1.1, RTE 1.1, Skynte 1.0 generators: **unchanged** (qualification
  fail-closed lives only in the new-die paths — qualification layer,
  endpoint, UI — never in the generators, so historical jobs reproduce)
- auto-bottom (`tuck_top_auto_bottom_carton` 1.0/1.1): **excluded**,
  `MEASURED_REFERENCE_REQUIRED`, has no adapter (endpoint declines it)
- no provider calls; no artwork remapping; no Gate-2 approval

## Authority state (whole phase)

Every qualified archetype holds **only** `TECHNICALLY_QUALIFIED_DOMAIN`
over its published domain. No archetype is production-approved. RTE remains
PROVISIONAL. The two `PHYSICALLY_*` states and
`PRODUCTION_AUTHORIZED_BY_MANUFACTURER` remain withheld pending real
physical/manufacturer evidence, tracked per geometry hash / dimensional
family / board / manufacturer.

## Tests

Framework + 4 per-archetype suites (opposed, STE, Skynte, RTE) with
mirror-defect, boundary, golden-hash, byte-stability and endpoint
coverage. Full application suite green; ruff clean; no migration drift.
