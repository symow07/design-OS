# 37 · Preservation master (Round 1B/1C)

`apps/pipeline/services/round_master_flow.py (+3)` · chain step: **None (Round 1B/1C); one helper**

## What it does today (read from its code)
`round_master_flow` runs an owner-started master over RoundMaster rows (`start` :31, `run` :151, `retry`, `fail`,
`tag` hard-wired to r2-gloss); `round_master_art` the steps (panels, paid detail/layout/plates, `build_files` :620,
eye, jury, publish); `round_master_files.Surface` a six-layer builder on round_balm_master's; `round_master_calls`
`MasterContext(RoundContext)` with `masked_edit` (:30, an edit with no image guard). `digest` (:23) is a stable
sha256 of any JSON value; round_files_flow.fail names failures with it.

## The run ($0)
`digest` of a value; the master tests of the round flow file run.
Recorded in [runs/37.json](runs/37.json), made by `docs/consolidation/probe.py 37`. What came out:
- `digest`: 283881a283616dd557f8a0c482c53d64445b7615b507caf82d66f8302a2cb290
- `steps`: ["panels", "detail", "layout", "plates", "files", "eye", "jury", "publish"]
- own tests (test_round_flow.py, -k "master"): **6 passed, 35 deselected, 5 warnings in 13.10s**
- seconds: 14.1; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: `digest`. Old: the Round 1B/1C master path; its pages are the round page's master links.

## Parts worth keeping
- `digest` — used by round_files_flow.
