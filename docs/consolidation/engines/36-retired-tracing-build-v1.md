# 36 · Retired picture-tracing build (v1)

`archive/round_files_v1` · chain step: **None (retired 2026-10-28)**

## What it does today (read from its code)
Nine modules in archive/round_files_v1 (art, line_fit, refinement_v2, repair_art, detail, attempt, attempt_art,
width_authority, extension) that traced and line-fitted the picked 3D picture onto the die; already out of the import
path, its tests beside it.

## The run ($0)
Each archived module compiled, and its import from apps tried.
Recorded in [runs/36.json](runs/36.json), made by `docs/consolidation/probe.py 36`. What came out:
- `round_files_art`: {"compiles": true, "importable_from_apps": false}
- `round_files_attempt`: {"compiles": true, "importable_from_apps": false}
- `round_files_attempt_art`: {"compiles": true, "importable_from_apps": false}
- `round_files_detail`: {"compiles": true, "importable_from_apps": false}
- `round_files_extension`: {"compiles": true, "importable_from_apps": false}
- `round_files_line_fit`: {"compiles": true, "importable_from_apps": false}
- `round_files_refinement_v2`: {"compiles": true, "importable_from_apps": false}
- `round_files_repair_art`: {"compiles": true, "importable_from_apps": false}
- `round_files_width_authority`: {"compiles": true, "importable_from_apps": false}
- seconds: 0.0; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing; the die-first method replaced tracing.
