# 16 · Paid boundary

`apps/pipeline/services/round_calls.py (+1)` · chain step: **Paid calls (one spend cap per round)**

## What it does today (read from its code)
`RoundContext` (round_calls.py:167) is every round's paid boundary: `text_call` (:348, up to 2–3 attempts, adaptive
thinking settings, one reservation per delivery), `image_call` (:467, the masked edit with the approved logo pinned),
`streamed_edit` (:39, partial images so a tunnel cannot cut a silent connection), `retained_verdict` (:148, a reply an
older parser could not read), `scoped_spend` (:114, the round's cap). spend_reservation.py is the ledger: `reserve`,
`settle`, `paid_operation`, `close_unknown`, `totals`. It parses replies with round_balm_calls.parse_response_text and
downloads with pipeline.agents.image_producer.download_image_bytes.

## The run ($0)
Every saved text reply of round 3 parsed again by the boundary's parser; the ledger's totals read (no call made); the
paid-boundary tests run.
Recorded in [runs/16.json](runs/16.json), made by `docs/consolidation/probe.py 16`. What came out:
- `saved_replies_parsed`: 7
- `saved_replies_refused`: []
- `ledger_totals`: {"today_usd_accounted": 4.447301, "total_usd_accounted": 97.677781, "unresolved_calls": 14, "day_cap_usd": 25, "total_cap_usd": 250}
- own tests (test_round_calls.py): **133 passed in 2.27s**
- seconds: 3.1; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `RoundContext.text_call`, `image_call`, `streamed_edit`, `retained_verdict`, `scoped_spend`.
- `spend_reservation.reserve/settle/paid_operation/close_unknown/totals` — the ledger.
