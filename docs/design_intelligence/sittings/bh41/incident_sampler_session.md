# §BH41(1) — INSTRUMENT INCIDENT, recorded: the sampler's own session blocked the test database's drop

The first persistent sampler (one `psql … \watch` session ON test_bbrose_db) stayed connected while pytest-django
dropped the test database at the end of the natural run A_nothing/1 (46 passed): the DROP failed ("being
accessed by other users — 1 other session"), the database was left behind, and the first amplified run
(D_amplified/run_1) then errored on every test — `DuplicateDatabase: database "test_bbrose_db" already
exists` → Django's interactive destroy prompt → `SystemExit: 2` → 46 errors in 486.94s, `BH41_AMPLIFIER
fired=0`. Not the deadlock shape; the sampler's fault, found by the run itself. The job was stopped (exit
144), the lingering psql session (pid 10294) killed, the stale database dropped by hand, and the sampler
rewritten to watch from the maintenance database `postgres` (pg_stat_activity / pg_locks are cluster-wide;
relation OIDs are named through a one-shot dump of the test database's pg_class). Every runner now passes
`--create-db`. The D_amplified/ directory keeps the failed attempt; the re-run is D_amplified2/.
Lesson for the register: a measurement instrument must never hold a session on the object it measures at
the moment that object is torn down — the same shape as the §BH24 cascade, one level up.

## Second instrument incident: a killed runner's next run survived the kill and collided with the next control

Stopping the first negative-control job (E_after_fix) with `pkill -f repro_run_amp.sh` ended the loop script,
but the pytest it had launched ran on and a further run (E_after_fix/run_3.txt, 07:39–07:43Z) still started —
overlapping E2_after_fix/run_1 (07:39:58–07:44:28Z) on the same test database. The sampler saw a
`CREATE TABLE "accounts_decisionchainhead"` at 07:43:00Z inside E2's run: the stray session's `--create-db`
dropped and recreated test_bbrose_db under the measured run. Result: 17 ProgrammingError/OperationalError
errors (tables gone), two requests stuck mid-handling beyond the 25 s bound (LiveServerNotDrained ×2, correct
behaviour of the drain against a database being rebuilt underneath it), 0 deadlocks, 0 flush errors, 0 setUp
collisions. E2 run 1 is EXCLUDED from the control as contaminated by the instrument; runs 2–10 (no other
session alive, verified by `ps` with start times) count, and a further clean run completes the ten. Lesson: a
runner is stopped by killing its process group and then PROVING by process start times that no pytest
remains before the next run starts — not by the kill's return.
