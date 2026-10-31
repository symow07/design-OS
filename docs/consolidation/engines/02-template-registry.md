# 2 · Template registry

`apps/dielines/registry.py` · chain step: **Die solving and cartons (which template and version)**

## What it does today (read from its code)
`_register` (registry.py:253) is the only way a template is published; `resolve(id, version=None)` (:800) returns the
current version when unpinned and raises on an unknown id or a missing pinned version (no fallback). The 1.1–1.4 carton
versions are derived by `_corrected`, `_d_derived_version`, `_print_ready_version` and `_trade_version` (:373–:471).
`production_templates` (:842) lists current versions only. The stand die is registered twice under one id:
counter_tray_header 0.1 is current and provisional (:713); 1.0 is production-ready but `current=False` (:762), so an
unpinned caller gets 0.1.

## The run ($0)
Every published template listed with the version an unpinned caller gets and its production flag; 1.0 resolved by
pin; the registry's two test files run.
Recorded in [runs/02.json](runs/02.json), made by `docs/consolidation/probe.py 2`. What came out:
- `templates`: 7
- `rows`: [{"id": "counter_tray_header", "version": "0.1", "production_ready": false}, {"id": "ecma_a20_20_01_01_ste_carton", "version": "0.1", "production_ready": false}, {"id": "reference_opposed_tuck_carton", "version": "0.1", "producti…
- `unpinned_gets`: {"counter_tray_header": "0.1", "ecma_a20_20_01_01_ste_carton": "0.1", "reference_opposed_tuck_carton": "0.1", "reverse_tuck_end_carton": "1.1", "skynte_foundation_tuck_carton": "1.0", "straight_tuck_end_carton": "1.1", "tuck_top_…
- `production`: [["reverse_tuck_end_carton", "1.1"], ["skynte_foundation_tuck_carton", "1.0"], ["straight_tuck_end_carton", "1.1"]]
- `counter_tray_header_1_0`: {"production_ready": true}
- own tests (test_registry.py, test_template_registry_agreement.py): **25 passed in 0.29s**
- seconds: 1.0; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: resolution and derivation. Wrong today: the stand die's current version is the provisional 0.1, so an unpinned
`resolve('counter_tray_header')` gives the wrong die; 1.0 must be current once 0.1's solver is gone.

## Parts worth keeping
- `resolve` — exact pinning, fails closed.
- `_trade_version` / `_print_ready_version` — versions derived from one base, not copied.
- `production_templates`, `is_production_eligible`.
