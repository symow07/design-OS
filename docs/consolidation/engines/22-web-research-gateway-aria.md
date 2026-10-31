# 22 · Web research gateway (ARIA)

`apps/pipeline/services/web_research.py` · chain step: **None directly; Tavily imports its policy helpers**

## What it does today (read from its code)
A policy layer: `check_url_policy` (:96, scheme and private-address block), `robots_rules`/`robots_file`/`robots_verdict`
(:156–:230), `governed_fetch` (:308, redirects checked hop by hop, robots, a MIME allow-list, a byte cap, the body's
sha256), `normalize_url` (:290), `html_to_text`, `classify_tier`, `quarantine_write`. Its own search, `run_search`
(:462), always raises: no provider has a connector here, so `run_research_session` (:476) can only end BLOCKED.

## The run ($0)
Each of round 3's research sources normalised and checked against the URL policy; its own search tried; its tests run.
Recorded in [runs/22.json](runs/22.json), made by `docs/consolidation/probe.py 22`. What came out:
- `sources`: 19
- `policy_allowed`: 19
- `policy_refused`: []
- `run_search`: {"error": "WebPolicyError: search provider 'tavily' has no connector"}
- own tests (test_2c2a_web_research.py): **13 passed in 3.40s**
- seconds: 18.9; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the policy helpers. Broken by design: `run_search` has no connector, so its research session cannot run.

## Parts worth keeping
- `governed_fetch`, `check_url_policy`, `normalize_url`, the robots helpers — imported by the Tavily connector.
