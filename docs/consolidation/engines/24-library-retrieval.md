# 24 · Library retrieval

`apps/pipeline/services/materials_retrieval.py (+2)` · chain step: **Research (the house library) and the boards' references**

## What it does today (read from its code)
`materials_previews.run` (:148) renders one 1,600 px preview per unique house file; `materials_captions.run` (:138) is
the paid captioning (Day 7) and `build_index` (:282) merges captions, measured colours and rights into the materials
index; `materials_retrieval` reads it: `cards` (:104), `score` (:141), `rank` (:178), `select` (:191), `candidates`
(:225), `index_row` (:119). The designer flow's `library_matches` uses the dashboard's `materials_library.search_index`
and `preview_file`, and only `index_row` from here.

## The run ($0)
The materials index's size; the dashboard's search run for round 3's words and each shade colour; the library's golden
tests run.
Recorded in [runs/24.json](runs/24.json), made by `docs/consolidation/probe.py 24`. What came out:
- `index_rows`: 10002
- `search_hits`: {"#C9707A": 4, "#8E4A5C": 4, "#C2553A": 4, "words": 4}
- own tests (test_day7_library_golden.py): **4 passed, 5 warnings in 0.68s**
- seconds: 1.6; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the index and `index_row`. Unused by the chain: `rank`, `select`, `candidates` (the older ConceptReference path).

## Parts worth keeping
- `index_row`, the index and its previews — what library_matches reads.
- `build_index` — how the index is made.
