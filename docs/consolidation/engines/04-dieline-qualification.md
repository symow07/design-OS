# 4 · Dieline qualification

`apps/dielines/qualification/runner.py (+3)` · chain step: **Cartons (qualified before production)**

## What it does today (read from its code)
`runner.qualify(user, adapter)` (runner.py:162) evaluates the dimension domain, draws the die through
`calculate_dieline`, runs `invariants.check_invariants` and the adapter's collision report, and returns a
`QualificationResult` (supported, violations, geometry hash). `qualification_matrix` (:223) runs the committed fixtures
(with `render_dir`, an SVG and a folded diagnostic per case); `seeded_property_sweep` (:272) is a seeded random sweep.
`fold_check.check(coords)` (geometry/fold_check.py:39) is a pure fold test of one carton. `closure.py` holds
declarations only. `adapter_for` (:139) has six adapters: none for the 1.3/1.4 trade tuck, ECMA or the stand.

## The run ($0)
Round 3's bottle qualified on every registered adapter; the framework's and the opposed tuck's qualification tests run.
Recorded in [runs/04.json](runs/04.json), made by `docs/consolidation/probe.py 4`. What came out:
- `qualified`:
  - reference_opposed_tuck_carton: {"error": "KeyError: 'safe_margin_mm'"}
  - reverse_tuck_end_carton: {"error": "KeyError: 'safe_margin_mm'"}
  - reverse_tuck_end_carton@1.2: {"error": "KeyError: 'safe_margin_mm'"}
  - skynte_foundation_tuck_carton: {"error": "KeyError: 'safe_margin_mm'"}
  - straight_tuck_end_carton: {"error": "KeyError: 'safe_margin_mm'"}
  - straight_tuck_end_carton@1.2: {"error": "KeyError: 'safe_margin_mm'"}
- own tests (test_qualification_framework.py, test_opposed_tuck_qualification.py): **20 passed, 8 warnings in 4.96s**
- seconds: 5.9; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: `fold_check.check` and the qualify sequence. Missing: no adapter for the 1.4 trade tuck the goal's cartons use,
so the qualification never sees the cartons that would print.

## Parts worth keeping
- `fold_check.check` — a pure, fast fold test the trade tuck tests already use.
- `qualify` + `check_invariants` — the domain → die → invariants → collisions sequence.
