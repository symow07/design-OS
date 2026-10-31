# 53 · IRE composer and emitters

`apps/ire/compose.py (+3)` · chain step: **Make my files (one part: Illustrator's save and reopen)**

## What it does today (read from its code)
`compose.compose_components_graph` (:203) builds the old pipeline's design graph per carton panel; `pdf_ai.emit_pdf_ai`
(:51) writes a PDF-compatible .ai with ReportLab; `native_ai.tree`/`script`/`build` (:898–:1443) drive Illustrator
through JSX; `illustrator_exec.illustrator_available` (:23) and `run_jsx` (:38) run a script through osascript — the
round writer's `native_roundtrip` uses `run_jsx`.

## The run ($0)
Illustrator present on this machine; the .ai emitter's tests run.
Recorded in [runs/53.json](runs/53.json), made by `docs/consolidation/probe.py 53`. What came out:
- `illustrator_available`: true
- own tests (test_pdf_ai_emitter.py): **74 passed, 6 skipped in 6.21s**
- seconds: 7.3; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: `run_jsx`. Old: the design-graph composer and the emitters (the old pipeline's).

## Parts worth keeping
- `illustrator_exec.run_jsx`, `illustrator_available` — Illustrator's own save and reopen.
