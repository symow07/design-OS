# §BH41 GOAL REPORT — THE FLUSH DEADLOCK, ROOT CAUSE

Owner goal §BH41 (OWNER_BLOCKER_CLEARANCE.md:20121–20213, T41 landed 08a7c45, 8/8). Every number below is measured
and sits in a file under `~/bh41_work/` (the captures under `repro/`, the scores and seals beside this report) or
in a gate capture under `bbrose_design_os/.tier2_captures/`.

## (1) REPRODUCED DETERMINISTICALLY — the measurements

### 1c. The mechanism proof — deterministic, one test, one flush
`~/bh41_work/test_bh41_mechanism.py` (outside the repo, run against the pytest-created test database): a second
backend holds AccessShareLock on the LAST table of this process's flush order (`accounts_decisionevent`) and,
0.8 s after Django's own `flush` command starts in another thread, asks for the FIRST (`intelligence_corpusitem`).
Result: `CommandError: Database test_bbrose_db couldn't be flushed` caused by `deadlock detected — Process 6770
waits for AccessExclusiveLock on relation 55332370 [accounts_decisionevent] … blocked by process 6769. Process
6769 waits for AccessShareLock on relation 55332614 [intelligence_corpusitem] … blocked by process 6770`; the
TRUNCATE side aborted (1.165 s, the deadlock_timeout), the second SELECT then succeeded (0.356 s). The seven
captures' shape, to the letter; 70 tables in the flush.

### 1d. The three ruled hypothesis runs, and the amplified one — counts
Targets: the two refusing files (`test_browser_review_board_references.py`, 12 tests; `test_browser_profile_editor.py`,
34 tests) under the gate's own form (`pytest … -q -p no:randomly`, one process, `--create-db`), the sampler beside
each run (`pg_sampler2.sh`: one persistent session on the maintenance database, pg_stat_activity ⋈ pg_locks every
100 ms, relations named through the test database's pg_class map).

| condition | runs | tests | deadlock events | runs with ≥ 1 | the pairs (flush waits for X, held by a request; the request waits for Y, held by the flush) |
|---|---|---|---|---|---|
| A — NOTHING beside the run | 10 | 460 | **1** | 1 (run 2) | pipeline_taskreference → pipeline_designtask ×1 |
| B — a Django shell connection open beside (`manage.py shell`, a cursor executed, held for the whole run on the configured database `bbrose_db`) | 10 | 460 | **1** | 1 (run 2) | pipeline_taskreference → pipeline_designtask ×1 — the same natural race at the same rate as A |
| C — a second pytest process beside (a loop of `pytest apps/core` sessions) | 2 | — | **0** | 0 | a DIFFERENT shape, not the deadlock: the two sessions share the one test-database name and destroy each other's database — `DuplicateDatabase`, `ObjectInUse` ("being accessed by other users"), `database "test_bbrose_db" does not exist` (92×), `OperationalError`/`ProgrammingError`; run 1 never reached a summary (21 min, an Internal Server Error on `/api/stats/`), run 2 errored all 46 tests in 3.9 s |
| D — the amplifier: 16 authenticated GETs to the page's own endpoints fired at every teardown, just before the contexts close | 10 | 460 | **75** | 8 | auth_group → auth_user_groups ×46; pipeline_designtask → core_product ×18; pipeline_designtask → auth_user ×11 |

A reproduces the suite's own race at its natural rate with nothing beside it: run 2 failed
`ReviewBoardReferenceBrowserTests::test_references_stay_separate_from_concepts` (its teardown flush) and the NEXT
collected test, `ProfileEditorBrowserTests::test_confirmed_task_shows_confirmed_state_not_the_editor` (its setUp,
UniqueViolation) — two consecutive ids across two files, the captures' shape. The sampler had it: backend 28325
`TRUNCATE "auth_permission", "pipeline_batchrun", "accounts_reviewerroleassignment", "pipeline_designtask", …` waits
for `pipeline_taskreference`; backend 28334 `SELECT "pipeline_taskreference"."id", "pipeline_taskreference"."task_id",
"pipeline_taskreference"."kind", "pipeline_taskreference"."image", …` (query_start 14:59:11.736, one millisecond after
the TRUNCATE's 14:59:11.735) holds AccessShareLock on `pipeline_taskreference` and wants `pipeline_designtask`
(the TRUNCATE's fourth table). That pair's OID difference is 226 — the difference in all five review-board captures
(20260812 ×2, 20260813, 20260905, 20260908); `auth_user_groups − auth_group` is 22 — the difference in both
profile-editor captures (20260827, 20260901). The base rate the ledger gives: four deadlocked gates in the 96
tier-2 runs since 2026-08-27 (≈ 207 live-server flushes each).

D makes the same race frequent: 75 events in 460 tests, 149 failures; per run 11, 17, 7, 4, 8, 15, 12, 0, 1, 0 —
the per-process spread is the flush's SET order (a pair deadlocks only when the TRUNCATE lists the request's
second table before its first), which `django_table_names` fixes per process and PYTHONHASHSEED varies between
processes. Every sampled event names the same three statements: the role check
`SELECT 1 AS "a" FROM "auth_group" INNER JOIN "auth_user_groups" …` (`permissions.py:28`, every authenticated
request), the task list `SELECT "pipeline_designtask"… ` joined to `core_product` / `auth_user`
(`views.py:1905`, `select_related('product', 'created_by')`), and — in the natural event — the references query.

## (2) THE CAUSE, file:line

**What holds the lock the flush deadlocks against:** a request thread of the test's own live server, executing
ONE autocommit statement — in every sampled event the role check
`SELECT 1 AS "a" FROM "auth_group" INNER JOIN "auth_user_groups" ON ("auth_group"."id" =
"auth_user_groups"."group_id") WHERE ("auth_user_groups"."user_id" = 1 AND "auth_group"."name" IN (…))`
— issued by `apps/pipeline/permissions.py:28` (`user.groups.filter(name__in=roles).exists()` in
`user_has_role`, :22–28), which every authenticated request runs: the DRF `IsTeamMember` permission
(permissions.py:74–87) on the task list, status and reference endpoints (views.py:240, :1897, :1918), the
function-view mirror `_team_member_required` (live_views.py:85–95) on `/api/stats/` and the event stream, and
the dashboard page's own reads (dashboard/views.py:34–48). PostgreSQL takes the statement's relation locks at
parse time in FROM order: AccessShareLock on `auth_group` FIRST, then `auth_user_groups`. The test's teardown
flush — `django/test/testcases.py:419 _setup_and_call → :1279 _post_teardown → :1313 _fixture_teardown →
call_command("flush")` → `django/core/management/commands/flush.py:73 execute_sql_flush` → ONE
`TRUNCATE t1, t2, …` (`django/db/backends/postgresql/operations.py:210–224`) — takes AccessExclusiveLock on
every table in the order `django_table_names` yields (`django/core/management/sql.py:11–19` →
`django/db/backends/base/introspection.py:98–114`: `tables = set()` … `list(tables)` — a SET order, fixed
per process and different between processes). When that order has `auth_user_groups` before `auth_group`
and the request's statement starts inside the TRUNCATE's lock-acquisition window (the sampled event: both
`query_start` at 14:46:56.885), the request holds `auth_group` and waits for `auth_user_groups`, the TRUNCATE
holds `auth_user_groups` (and forty-odd others) and waits for `auth_group`: the two-backend cycle. PostgreSQL's
detector (deadlock_timeout 1 s) aborts the TRUNCATE — the same victim in all seven captures and every
sampled event — as `DeadlockDetected`. Other request threads in the same moment wait on `auth_user` or
`core_product` holding nothing; they are queued, not deadlocked.

**Why the request is still running when the flush starts:** the live server (`django/test/testcases.py:1752
LiveServerThread` → `django/core/servers/basehttp.py:86 ThreadedWSGIServer`, `daemon_threads = True`) runs
each request in its own thread with its OWN PostgreSQL connection (`connections_override` exists only for
in-memory SQLite, testcases.py:1836–1843) and closes that connection in `close_request` (basehttp.py:109–111),
AFTER the view has run. The harness's `tearDown` (`apps/pipeline/tests/test_browser_staged_reference_ui.py:76–78`)
closes the browser contexts — the CLIENT side of every request the page had in flight: its initial loads and
its own polls (`static/js/poll.js:22` `/api/stats/` every 5 s, `:72` `/api/notifications/` every 10 s, and
`:426`/`:540` the event stream and status polling for working tasks) — and returns at once; Django's
`_post_teardown` then flushes immediately. Nothing in Django or the harness waits for the server's request
threads to finish. The gate runs one process (`tools/tier2_gate.py:49–50`, no xdist), so the race is
intrinsic to a single pytest process; no second process, shell or gate neighbour is needed.

**Why the cascade then dirties the database for later setUps:** the aborted TRUNCATE rolls back — nothing
is truncated — and `flush.py:75` raises `CommandError: Database test_bbrose_db couldn't be flushed`, which
`_fixture_teardown` propagates and Django does not retry; the finished test's rows stay. The next test's
`setUp` (`test_browser_staged_reference_ui.py:67`, `User.objects.create_user("uib4b", …)`) inserts the same
username into the un-flushed `auth_user` → `UniqueViolation auth_user_username_key`. That test's own
teardown flush then succeeds (no request is in flight at that instant) and the suite continues — which is
why every event costs exactly two consecutive ids, the shape of all four refusals.

## (3) THE FIX — the drained live server (own commit 6ad65f0, predicted-then-scored 8/8 on pred_fix4; attempts 1–3 sealed and scored as history without a gate: score_fix_attempt1–3.txt)

**Shape — the first the ruling lists, "closing the live-server thread's connection before flush":**
`apps/pipeline/tests/browser_live_server.py`. `DrainableWSGIServer(ThreadedWSGIServer)` counts a request from its
ACCEPT (`process_request`, the server's own loop) until `process_request_thread` returns — i.e. after
`close_request` has closed that thread's PostgreSQL connection and released every lock it held.
`wait_idle(timeout)` blocks until no BLOCKING request remains and none arrives for a 50 ms quiet window, and raises
`LiveServerNotDrained` — naming each remaining request's client, age and whether its client has gone, and the
handler threads' frames — when the bound expires: fast, named, never a cascade. Blocking = every request younger
than `stream_seconds` (2 s) and every older one whose client is still connected; an older request whose client has
gone is a streaming response and is tolerated (measured unendable from the server: the first write after a client's
close still succeeds, only the second fails, the stream writes once per fifteen iterations, a server-side shutdown
raises ENOTCONN — it ends by itself or at the flush, and holds no lock between its single-table statements). `DrainedStaticLiveServerTestCase(StaticLiveServerTestCase)` carries the
server through `server_thread_class = DrainableLiveServerThread` and overrides `_post_teardown` to drain, then to prove on the test's own
connection that no other backend of the test database holds a relation lock (`pg_locks`, polled every 10 ms,
bounded, named on expiry), and only then to call `super()._post_teardown()`, which flushes; the flush ALWAYS runs — a drain that times out is raised after it, so a slow
request fails the test by name but never leaves rows for the next test's setUp. The drain bound is 25 s and the lock-check bound 10 s; neither is reached in the control.

**Scope:** every live-server class of the apps leg — 17 test classes in the 15 `test_browser_*.py` files and the
5 `*_screenshot_capture.py` harnesses — inherits `DrainedStaticLiveServerTestCase` instead of
`StaticLiveServerTestCase`: one import line and one base per file, 42 edits, nothing else touched
(`git diff`: 18 files 2+/2−, `test_browser_profile_editor.py` 4+/4−, `test_browser_staged_reference_ui.py`
90+/2− for the three tests below). No test file added: the suite manifest is untouched (`browser_live_server.py`
is not collected); the apps leg collects 7,778 → 7,781.

**Bars never lowered:** no test skipped or marked flaky; no retry anywhere; no isolation setting, lock timeout
or deadlock timeout changed; §BH24's id-list not widened (it is retired by (4)); the flush still runs after
every test, on the same connection, with the same TRUNCATE.

**Four browser-free tests** (`DrainedLiveServerTests` in `test_browser_staged_reference_ui.py`, no Playwright):
`wait_idle` returns only after a young in-flight handler whose client has gone finishes; a handler that outlives
the bound fails fast by name; an old silent abandoned stream is tolerated while a young one blocks; an idle
server drains in one quiet window. 4/4, repeated.

**The negative control** — the reproduction of (1), probabilistic, ten times each, the sampler beside every run:
| | runs | tests | deadlock events | runs refusing | LiveServerNotDrained |
|---|---|---|---|---|---|
| BEFORE the fix (D_amplified3) | 10 | 460 | 75 | 8 | — |
| AFTER the fix, attempt 1 (E_after_fix, run 1 only) | 1 | 46 | 0 | 0 | 2 (the 15 s bound on the event stream; the flush was skipped → 2 setUp UniqueViolations of my own) |
| AFTER, attempt 2 (E2_after_fix, runs 2–4; run 1 contaminated by a survivor of the killed E job) | 3 | 138 | 0 | 0 | 5 (the 25 s bound on the abandoned event stream; the flush ran) |
| AFTER, attempt 3 (E3_after_fix, runs 1–2) | 2 | 92 | 0 | 0 | 4 (same; the stream cannot be ended from the server — measured) |
| AFTER, attempt 4 — the landed shape (E4_after_fix) | 10 | 460 | **0** | **0** (10 green) | **0** |
The drain's cost, measured over the 460 teardowns of E4: median 0.088 s, p90 0.101 s, max 1.893 s per teardown (the maximum is a teardown that waited for a young request whose client had gone to finish, or for a stream to age past two seconds).

The mechanism proof (a second connection holding a lock outside the live server) stays reproducible by
construction — it proves the lock cycle, not the suite — and is not the control.

## (4) §BH24 SUPERSEDED

By the owner's §BH41 sentence — *"§BH24 SUPERSEDED: its bounded re-runs are retired by this sentence once (3)
lands; the standing rule becomes 'a flush deadlock is a defect, reproduce it'"* — the retirement takes effect at
the landing of the fix commit named in this report; the register's idiom governs how it is read (§BH9(b): the
superseding sentence lives in §BH41, no marker is placed on §BH24). The orphan ledger lines: the refusal of
2026-09-08 left ONE orphan on disk (485 vs 484 at HEAD); the gate stages the whole ledger at every landing, so it
folded into the first landing after the refusal — T41, 08a7c45 (484 → 486), as the transcription's reading
recorded; the three earlier refusals' orphans folded into the landings that followed them at the time (T35 run 2;
gate C attempt 2 under §BH24; the 2026-08-27 successor). No orphan remained to fold into the fix commit's landing
(486 → 487, its own line only). The reading is recorded, not resolved: if the owner meant the orphans held for
the fix commit, the sentence governs and the ledger cannot now be reordered (APPEND_ONLY).

## (5) THE GATES, THE STASH, THE INVARIANTS

**Gate 1 — nothing beside it:** the fix's own gate, launched 2026-09-08T08:14:49Z on the verified index, `TIER_2=GREEN collected=8594 failures=0 apps=7782 dip0c=671 dip0=141`, GEXIT=0, landed 6ad65f0 at 08:29:03Z; the ledger 486 → 487 (append-only); no flush deadlock.
**The apps leg under the reproducing load** (the load of (1) that reproduced is in-process — the amplifier plugin firing 16 authenticated requests at every live-server teardown — so it is run with the gate's own pytest form over the whole apps leg, `pytest apps -q -p no:randomly -p bh41_amplifier`, the sampler beside it; a shell connection and a second pytest process, the two external loads the ruling names, were measured in (1) as no factor and as a different collision respectively): `7778 passed, 4 skipped, 41596 subtests passed in 727.20s`, 0 failed, 0 errors; `BH41_AMPLIFIER fired=3008`; 207 drained teardowns, median 0.085 s, p90 0.097 s, max 1.920 s; 0 deadlock lines, 0 flush errors, 0 stalls (`repro/S_load/suite.txt`, sampler beside it). The same tree that refused four gates in this arc runs green under sixteen times the request load at every live-server teardown.
**The stash restored:** `git stash pop` of stash@{0} after the load run, the worktree clean: the stash's tree equalled the 298 entries recorded before the stash (path + blob), the index after the restore equals them, all 297 content files re-hashed at their `INDEX.json` `sha256_copy`, `INDEX.json` itself at its write-time sha256 (7ee60b263e820543); 298 rows staged again (`564838 insertions`), the stash list empty. Nothing under it was read or written between the stash and the restore; §BH40 resumes at (a) with this index.
**Invariants at 6ad65f0:** GATE 7fbeb8f1fe10b0fb [514:541] and TEST b32030dc827263e4 byte-identical; tree seals dip0c c22592930c75001c / dip0a d72072760ab20a6a; the eight M7 artefacts == baseline; the Noto trio VERIFIED_FOR_PRODUCTION and the 35 at their PROVENANCE hashes; Warm Gold #CBA87D in CS-001 and CS-002; WIT 864; the suite manifest untouched (browser_live_server.py is not a test file; the four tests joined an existing file); the register untouched (20,213 lines, db241ccf0b258e35); the DIP-0A inventory 3b3cfdc2bf4fc6c0.


## 6. Readings recorded for the owner's word (the sentence governs)

- **The four refusals and the eight ids.** The ruling counts four refusals on four ids; the captures give four refusals since 2026-08-27 on eight failing ids — two per event: the test whose own teardown flush deadlocked and the next collected test, whose setUp met the rows. Read as the four events; recorded, not resolved.
- **The orphan ledger lines.** One orphan existed at the ruling (485 vs 484) and folded into T41's landing (the first after its refusal, 484 → 486), because the gate stages the whole ledger at every landing; the three earlier orphans had folded into their own successors. None remained for the fix commit (486 → 487). If the owner meant them held for the fix commit, the ledger is APPEND_ONLY and cannot now be reordered.
- **"With the hypothesis load beside it."** The load that reproduced in (1) is in-process (the amplifier plugin); the two external loads the ruling names were measured as no factor (B) and as a different collision (C). The second proof therefore ran the whole apps leg under the amplifier with the gate's own pytest form, not as a second guarded commit; one commit gate ran with nothing beside it. If the owner wants the guarded gate itself run under an external load, one word names which.
- **The tolerated stream.** An abandoned event stream is tolerated after two seconds because it is measured unendable from the server and lock-free between its single-table statements; a future stream that JOINs would reintroduce the µs race behind the lock check. The lock check names it if it ever holds a lock at flush time; the SSE view itself (`live_views.py`) is untouched by this front — a product change (a heartbeat comment every second, which would let the server notice a gone client within a second) is one sentence away and was not made.
- **§BH24 retired.** By the owner's §BH41(4) at this landing; the register's idiom (§BH9(b)) governs the reading: no marker on §BH24.
- **The instrument incidents** (incident_sampler_session.md): the sampler's own session once blocked the test database's drop; a killed runner's child pytest twice survived the kill (a `pkill -f` pattern beginning with a dash is parsed as an option; the interpreter's argv reads `Python -m pytest`) and collided with the next control. Each was measured, excluded from the counts, and fixed in the instrument; `stop_runs.sh` now proves by process start times that nothing remains.
- **The five screenshot-capture harnesses** (`*_screenshot_capture.py`, not collected by the gate) were swapped with the test classes for consistency; if the owner meant the fix confined to collected tests, five two-line reverts.
