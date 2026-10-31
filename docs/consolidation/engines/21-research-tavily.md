# 21 · Research: Tavily

`apps/pipeline/services/web_research_tavily.py` · chain step: **Research (the web half)**

## What it does today (read from its code)
`TavilySearchConnector.search` (:111) checks the spend cap, reads the key, posts one search under `paid_operation` and
writes a ledger row; `normalize` (static) keeps results with their page and drops Tavily's own answer. The designer
flow uses only these two (round_designer.py:140, :159). The rest is the older product research: `run_tavily_session`
(:294, DB session rows and the pilot packet), `plan_queries_v2` (:62, twelve fixed queries about a rose night serum),
`_retain_results`, `_fetch_phase`, `_fetch_images` and `HostManners`, which the trend board uses.

## The run ($0)
Round 3's six saved searches read again (no search bought) and one reply normalised by the connector; the sources the
research kept counted; the Tavily tests run.
Recorded in [runs/21.json](runs/21.json), made by `docs/consolidation/probe.py 21`. What came out:
- `saved_searches`: 6
- `per_search`: [{"file": "1.json", "results": 5, "query": "lip gloss packaging and counter display design"}, {"file": "2.json", "results": 5, "query": "new lip gloss launches 2026"}, {"file": "3.json", "results": 5, "query": "lip gloss packagin…
- `research_sources_kept`: 19
- `normalize`: {"connector": "tavily_connector/1.0", "query": "lip gloss", "results": [{"query": "lip gloss", "rank": 1, "title": "T", "url": "https://a.example/x", "domain": "a.example", "snippet": "cccccccccccccccccccccccccccccccccccccccccccc…
- own tests (test_2c2a_tavily.py): **50 passed, 8 warnings in 11.33s**
- seconds: 12.4; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the connector. Old: the session, the fixed serum queries and the fetch phases (the trend board's path).

## Parts worth keeping
- `TavilySearchConnector.search` and `normalize` — the designer flow's six searches, metered and capped.
