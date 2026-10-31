# 23 · Trend board

`apps/pipeline/services/trend_board.py` · chain step: **None (round_designer.research does the designer flow's research)**

## What it does today (read from its code)
DB-bound on a design task of the old pipeline: `plan` (:392) scopes searches by platform; `build` (:465) creates a
TrendBoard and a research session, searches (Tavily), picks (`_pick` :543, caps per platform), fetches under robots
(`_fetch` :740) and reads pictures with a model (`_read` :971); `write_brief` (:1483) is one Claude call;
`mark_near_copies` (:1380, an 8 × 8 average hash).

## The run ($0)
Its tests (in the Tavily and container-target files) run; it needs a design task of the old pipeline to do more.
Recorded in [runs/23.json](runs/23.json), made by `docs/consolidation/probe.py 23`. What came out:
- own tests (test_2c2a_tavily.py, test_container_target.py, -k "trend or subject"): **28 passed, 62 deselected, 1 warning in 10.71s**
- seconds: 11.8; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs.
