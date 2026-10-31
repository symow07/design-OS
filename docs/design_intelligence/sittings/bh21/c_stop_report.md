# §BH23 HARD-STOP REPORT — GATE C (TRANSCRIPTION) REFUSED ON TWO REGISTERED-AT-ZERO FLAKES
2026-09-01. HEAD 00ab549 (A′, unmoved). Exit 1 hand-captured (c_exit.txt).
Durable copies: c_gate.log, c_exit.txt, c_preflight_ps.txt, c_post_ps.txt,
and the gate's own capture trio .tier2_captures/20260901T023609Z_00ab549*.

## 1. THE STOP
Gate C — the §BC transcription commit of §BH22+§BH23, register staged
+230 −0 — REFUSED:
  TIER_2=REFUSE collected=8490 failures=2 apps=7684 dip0c=671 dip0=135
  GUARDED_COMMIT_REFUSED: TIER_2=REFUSE (A326/3m)
  REGISTERED_AT_ZERO ×2: ConfirmationDialogBrowserTests::
    test_confirm_sends_one_request_and_freezes_into_confirmed_state
    test_dialog_traps_focus  — "being known about is not relief"
Suite summary: 2 failed, 7679 passed, 3 skipped, 41596 subtests, 693.06s.
§BH23's first stop — "a refusal on anything beyond the movers these
rulings exist to clear" — FIRED: neither test is a mover. Its fifth stop —
"a prediction miss that changes what the next step should do" — ALSO
FIRED: pred_c L6 predicted GREEN. Stopped; nothing further executed.

## 2. THE MECHANISM, MEASURED FROM THE CAPTURE
ONE root cause, two failures, in cascade:
  * Test 1: psycopg2.errors.DeadlockDetected during Django's between-test
    flush — `TRUNCATE "pipeline_designproject", …` — postgres backend
    10628 waits for AccessExclusiveLock, blocked by 10646, which waits for
    AccessShareLock, blocked by 10628. A lock CYCLE on the shared test DB.
  * Test 2: the deadlocked flush left the test DB un-truncated; the next
    test's setUp re-created its user into the dirty DB —
    UniqueViolation "auth_user_username_key", Key (username)=(uib4b).
Infrastructure/timing, not content: the staged commit is a git-root
markdown append the suite never imports. The gate-time worktree differed
from A′'s GREEN worktree (35 minutes earlier, same three test rows
unstaged) by exactly that ONE file — and these two tests PASSED there.

## 3. CONCURRENCY, ADJUDICATED FROM PRESERVED EVIDENCE
No second session: preflight measured py=0 seconds before launch
(c_preflight_ps.txt); the post-refusal snapshot's single "pytest" match is
MY OWN wrapper carrying an echo label (c_post_ps.txt — the label trap
recurred in my forensics command and was adjudicated from the preserved
snapshot, as the idiom is designed to allow; no real pytest existed);
ledger carries exactly ONE orphan, mine; the only new captures are mine.
The deadlock is between two backends of the SAME run — consistent with
the live-server thread's DB connection vs the flush TRUNCATE. The
register's cause stays UNESTABLISHED — one observation establishes
nothing, and I do not update the register (A191).

## 4. THE FLAKE REGISTER, READ ONLY
Both ids registered at BUILD SPRINT 13 / WI-V: cause UNESTABLISHED,
invocations_allowed 0, invocations_used 0 — "only the owner raises it
(A191)". Prior history (2026-08-27): both failed during the two-session
collision; register notes isolated greens establish nothing. The refusal
is the register working as designed.

## 5. REPO STATE AT THE STOP — NOTHING LOST
  * HEAD 00ab549 = A′, unmoved through the refusal.
  * INDEX INTACT: OWNER_BLOCKER_CLEARANCE.md still staged +230 −0 —
    placeholders resolved (5× 00ab549, owner's __P2HASH__ literal),
    16,494-line HEAD prefix byte-identical (rc=0), pure append proved.
  * Unstaged: the three tools/dip0c test rows (commit B's set) + the
    ledger orphan: 425 on disk / 424 committed — the refused run's own
    record_integrity verdict line (02:24:21Z). It STAYS (append-only);
    the next successful gate folds it (+2 instead of +1 for that commit).
  * pred_c stands as sealed; scored honestly: pre-gate legs L1-L4 and
    claims C1-C3 all HELD (append shape, staging, placeholder counts,
    verbatim proofs); L6 MISS (GREEN predicted, REFUSE measured on two
    non-mover registered-at-zero flakes); L5/L8/C4 not reached; C5's exit
    evidence captured (content: exit 1). No bar moved after the fact.

## 6. WHAT THE STOP DOES AND DOES NOT CHANGE
The §BH23 sequence C → B → D is prepared and untouched: the staged
register is byte-ready; b_msg/pred_b and d_msg/pred_d are drafted; the
queue block awaits only __P2HASH__/landing hashes. A′ and its two spent
single-use authorities are LANDED and unaffected. The goal state (gate
GREEN at final HEAD, worktree clean, queue record landed) is not reached.

## 7. OPTIONS — REPORTED, NOT DECIDED (a ruling is required to proceed)
  i.   Rule a RE-RUN of gate C unchanged: nothing of mine differs; the
       failure is a timing deadlock; A′'s gate passed both tests with the
       same content 35 minutes earlier. Cost per refused attempt: ~12 min
       + one ledger orphan (folded by the next landing). Risk: the flake
       can recur; each recurrence is another stop-and-report absent a
       standing sentence (e.g. "re-run on THESE TWO ids' infrastructure
       refusals, N times max, stop on anything else").
  ii.  Rule on the register (A191): raise invocations_allowed for the two
       ids — the register's designed relief path, owner-only.
  iii. Anything narrower; your sentence governs.

## 8. NOTHING ELSE
No file beyond the declared sets moved; no register/contract edit; the
OFL is unread; C3 blocking; the 21 untouched. The one §BH23 report
remains pending at the sequence's end — this stop report is delivered
because the stop fired, same as §BH22's.
