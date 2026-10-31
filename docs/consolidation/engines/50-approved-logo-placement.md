# 50 · Approved logo placement

`apps/pipeline/services/round_files_export.py` · chain step: **Logo**

## What it does today (read from its code)
The same module as row 35: `LOGO` (round_files_export.py:28, docs/brand/mark/bbrose-logo.svg) and `LOGO_SHA256` (:29)
pin the approved vector logo; `export_object` places each spec's `logos` and refuses a logo that is not the approved
file; the face builder's `marks` places the front strip's logo over its line inside the safe area.

## The run ($0)
The logo file against its pin; the writer's logo refusal test run.
Recorded in [runs/50.json](runs/50.json), made by `docs/consolidation/probe.py 50`. What came out:
- `logo`: bbrose_design_os/docs/brand/mark/bbrose-logo.svg
- `pinned`: ccf120cef3e8317d
- `file_matches`: true
- own tests (test_round_files_export.py, -k "logo"): **1 passed, 69 deselected, 5 warnings in 0.24s**
- seconds: 1.1; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `LOGO`, `LOGO_SHA256` and the placement in `export_object` and `marks`.
