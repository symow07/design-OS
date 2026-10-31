# Phase 2A-9D — STE/RTE 1.2 D-Derived Closure Correction — CLOSEOUT

Date: 2026-07-23. Five focused commits. New versions
`straight_tuck_end_carton/1.2` and `reverse_tuck_end_carton/1.2` correct
the 1.1 W-derived-tuck defect using the D-derived model validated by Skynte
1.0. 1.1 is byte-stable and remains the default; 1.2 is non-default,
`TECHNICALLY_QUALIFIED_DOMAIN` only.

## Commits

| # | hash | content |
|---|---|---|
| 1 | 7544c82 | shared D-derived closure model (engine `_closure_heights`, `_StyleConfig.closure_model`, v1.2 style configs for STE/RTE only) |
| 2 | c892682 | STE 1.2 registry def (non-current) + shared `dtuck_qual.py` + runner adapters + reports + 12 tests |
| 3 | 935d65f | RTE 1.2 qualification + independent mirror audit + reports + 12 tests |
| 4 | 99cf988 | endpoint optional `template_version` + 8 integration tests (no default switch) |
| 5 | (this) | comparison report, investigation/physical docs, closeout |

## Exact formulas (v1.2)

- major tuck reach: **`tuck_total = D + lip`**, `lip = 16 mm` (explicit
  frozen constant, informed by Skynte's validated DECISION-019 value;
  derived here independently for STE/RTE)
- shoulder span: **`curve_h = 0.5 × lip = 8 mm`** (lip-derived — always
  `< lip`, so it always fits; removes the W-derived shoulder and Skynte's
  width cap)
- shoulder inset: `W × 0.227` — flap-width geometry (the main-panel tuck
  is W wide); NOT a closure-depth dependency
- dust flap: `D × 0.631` (D-derived, unchanged from 1.1)
- everything else (panel order, friction slits `W × 0.327`, 2t lock
  notches, glue taper, bleed, per-hinge creases) identical to 1.1

## Supported domains

Both STE 1.2 and RTE 1.2: 1.1's domain **minus** `TUCK_LIP_VS_HEIGHT`
(fixed 16 mm lip < H/2 for any H ≥ 60) and **minus** `DUST_CLAMP_BOUNDARY`
(D+16 zone always exceeds the 0.631 D dust). Binding edges that remain:
`W ≥ 1.262 D` (dust clearance — **unchanged from 1.1**, shared with
Skynte), `H > W`, `H > D`, `D ≤ 2.5 W`, `D + t ≥ G + 3`, slit web ≥ 2 mm,
published ranges. 1.2 widens **only** in the wide-short (lip) direction.

## Property sweeps (deterministic, 0 failures)

| version | seed | in-domain | whole-space | supported | rejected |
|---|---|---|---|---|---|
| STE 1.2 | 20260726 | 150 | 250 | (see report) | (named constraints) |
| RTE 1.2 | 20260727 | 150 | 250 | (see report) | (named constraints) |

Both: **0 failures / 0 crashes**. Fixture matrices: 12 each, 10 supported;
the wide-short (90×25×92) and large-shallow (200×40×250) cartons STE 1.1
rejected are now SUPPORTED — the defect removal, proven.

## 1.1 vs 1.2

`ste_rte_1_1_vs_1_2_comparison.md`: 1.2 content hashes differ from 1.1 for
every carton (not backward-compatible output). Defect removed for
shallow/wide-short; dust-clearance edge unchanged (square 28×28×120 still
rejected by both).

## Mirror audit (RTE 1.2) — independent, clean

Top tuck over FRONT column, bottom over BACK, slits on mirrored panels,
flat + cut area identical to STE 1.2 at the same dims. No coordinate sign
or local-origin error.

## Versioning behavior

- STE/RTE resolve to **1.1** unpinned; 1.2 reachable only by explicit pin.
- 1.2 `production_ready=False`, `PHYSICAL_SAMPLE_VALIDATION_REQUIRED`.
- No automatic migration; 1.1 not superseded for existing/pinned tasks.
- Default selection **unchanged**; UI unchanged (endpoint qualifies 1.2
  only on an explicit `template_version`).

## Authority states

STE 1.2 and RTE 1.2: `TECHNICALLY_QUALIFIED_DOMAIN` only. Not granted:
`PHYSICALLY_VALIDATED_INSTANCE`, `PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY`,
`PRODUCTION_AUTHORIZED_BY_MANUFACTURER`. Independent physical-test matrices
proposed for both (no samples approved).

## Non-regression

- task #47 (Skynte) hash `2be58c7b…` and task #50 (opposed) hash
  `0f5b8bf6…`: unchanged; task #50 stays `APPROVED_FOR_PHYSICAL_TEST`, not
  `PHYSICALLY_VALIDATED_INSTANCE`; no artwork remap; test PDF not
  regenerated; Gate 2 not approved.
- STE 1.1 / RTE 1.1 content hashes byte-stable; Skynte 1.0 unchanged
  (separate module — the engine branch cannot reach it).
- auto-bottom (1.0/1.1) excluded, `MEASURED_REFERENCE_REQUIRED`, no
  adapter at any version.
- no provider calls anywhere in the phase.

## Stop

Stopping before the §17 actions: preferring 1.2 for new tasks,
deprecating 1.1 in the UI, remapping any task, or granting physical/
production authority — each awaits separate approval.
