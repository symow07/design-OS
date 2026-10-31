# 12 · Round state machine and runner

`apps/pipeline/services/round_flow.py` · chain step: **Runs every step of the ideas half as a worker job**

## What it does today (read from its code)
`create_round` (:199) writes the brief and the first step; `run_step_job` (:466) runs one step under the round's lock
(dispatching to round_designer, round_ideas or round_steps by the brief's flow), records failures, commits the
round's records (`commit_artifacts` :118) and queues the next step; `submit_pick` (:629), `submit_board_pick` (:659),
`none_of_these` (:694), `retry_round` (:735), `summary` (:773). It imports Round 1/2's sheet, product brief, report and
steps for the older flows.

## The run ($0)
Round 3's brief: is it a designer round, and its steps; the round flow file's tests run.
Recorded in [runs/12.json](runs/12.json), made by `docs/consolidation/probe.py 12`. What came out:
- `designer_round`: true
- `steps`: ["research", "boards", "board_pick", "designs", "pick_page", "pick"]
- own tests (test_round_flow.py): **41 passed, 7 warnings in 23.24s**
- seconds: 24.5; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `run_step_job`, `create_round`, `submit_board_pick`, `submit_pick`, `none_of_these`, `retry_round` — the runner.
- `write_json`, `append_json`, `round_root`, `commit_artifacts` — the records every step writes.
