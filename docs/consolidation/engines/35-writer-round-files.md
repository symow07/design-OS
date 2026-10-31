# 35 · Writer (round files)

`apps/pipeline/services/round_files_export.py` · chain step: **Make my files (the layered .ai, live type, the logo)**

## What it does today (read from its code)
`export_object(spec, folder, native=)` (:1023) writes one object as a six-layer 1:1 .ai: the raster artwork, live type
in the two pinned fonts (`font_records` :56 checks each against the GRANTED census and its pin), the approved logo by
its pin (`LOGO`, `LOGO_SHA256`), foil, the die locked; `measure_type`/`fit_type_envelope` (:185, :233) keep each word
in its box; `read_back_ai` (:714) re-reads layers, type, colours and the die; `native_roundtrip` (:920) has Illustrator
save and reopen it (ire.handoff.illustrator_exec.run_jsx). It takes FONT_PATHS, `rgb`, `glyph_metrics`, `shaped` and
`set_layers` from round_balm_master.

## The run ($0)
Round 3's drawn header face written as a layered .ai with its live type and the logo (Illustrator's save not run here)
and read back; the writer's tests run.
Recorded in [runs/35.json](runs/35.json), made by `docs/consolidation/probe.py 35`. What came out:
- `logo_sha_ok`: true
- `font_records`: {"latin": null, "arabic": null}
- `header_ai`: {"ai": "header-probe.ai", "type_runs": 9, "logos": 0, "checks_failed": [], "checks": 15}
- own tests (test_round_files_export.py): **64 passed, 6 skipped, 5 warnings in 10.60s**
- seconds: 13.1; files written: 5 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `export_object`, `font_records`, `measure_type`, `measure_turned_type`, `fit_type_envelope`, `read_back_ai`,
  `render_flat`, `native_roundtrip`.
