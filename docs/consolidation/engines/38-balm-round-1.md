# 38 · Balm round (Round 1)

`apps/pipeline/services/round_balm_master.py (+13)` · chain step: **None (Round 1); the type helpers and the parser**

## What it does today (read from its code)
Fourteen modules for Round 1's lip balm (calls, master, sheet, finish, carton, run, close, review, page, …), all pinned
to docs/rounds/r1-balm. Still used by the chain: `glyph_metrics(copy, face)` (round_balm_master.py:49, fontTools
bounds and advance of a shaped string), `shaped` (Arabic reshaped and ordered), `FONT_PATHS`, `rgb`, `set_layers`
(the writer and the face builder use them) and `parse_response_text` (round_balm_calls.py:50, exactly one JSON fence or
plain JSON; the paid boundary, round_ideas and the jury completion use it).

## The run ($0)
`glyph_metrics` of BBROSE and ملمع شفاه in the two pinned faces; `parse_response_text` on a fenced reply and on two
fences; the balm tests run.
Recorded in [runs/38.json](runs/38.json), made by `docs/consolidation/probe.py 38`. What came out:
- `latin`: {"box_em": [0.074, -0.012, 3.666, 0.712], "advance_em": 3.723, "missing": []}
- `arabic`: {"box_em": [0.055, -0.377, 4.65, 0.776], "advance_em": 4.697, "missing": []}
- `fence`: {"a": 1}
- `two_fences`: {"error": "ValueError: Ambiguous or incomplete JSON fence"}
- own tests (test_round_balm.py, test_round_balm_preservation.py): **48 passed, 5 warnings in 1.87s**
- seconds: 2.8; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the six helpers above. Old: Round 1's balm flow.

## Parts worth keeping
- `glyph_metrics`, `shaped`, `FONT_PATHS`, `rgb`, `set_layers` — live type's metrics and the layers.
- `parse_response_text` — the one reply parser.
