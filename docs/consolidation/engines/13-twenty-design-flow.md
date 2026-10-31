# 13 · Twenty-design flow

`apps/pipeline/services/round_ideas.py` · chain step: **None (replaced by the designer flow); five helpers**

## What it does today (read from its code)
`seeds` (:108, one paid text call for twenty ids), `designs` (:182, twenty pictures), `pairwise` (:232, a two-juror
jury over 190 pairs), `pick_page` (:278), `finalize_pick` (:299). Still used: `COPY_START`/`COPY_END` (:26–27, the
delimiters that keep printed copy apart from instructions), `_line` (:43), `_validation` (:34, rejects a paid reply
that does not validate), `read` (:30) and `record_break` (:328, appends a failure to BREAKS.md once, under a lock).

## The run ($0)
Its pair plan for twenty ids; the ideas tests of the media round file run.
Recorded in [runs/13.json](runs/13.json), made by `docs/consolidation/probe.py 13`. What came out:
- `batches`: 5
- `pairs`: 190
- `steps`: ["seeds", "designs", "pairwise", "pick_page", "pick"]
- own tests (test_product_round_media.py, -k "ideas"): **7 passed, 65 deselected in 2.80s**
- seconds: 3.8; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the five helpers. The twenty-design flow itself is never started (New design is the designer flow).

## Parts worth keeping
- `COPY_START`/`COPY_END`, `_line`, `_validation`, `read` — used by round_designer.
- `record_break` — used by round_flow and round_files_flow.
