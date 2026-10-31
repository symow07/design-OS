§BH20(b) REGENERATION DECLARATION — SEALED BEFORE EXECUTION, PER §BH19(b) DISCIPLINE
====================================================================================
STATUS: SEALED 2026-08-31T09:33:52Z, before execution. Nothing below the
EXPECTATIONS heading changed at seal time; only the measured "before" values
were added to the SEAL block. Hash method (self-consistent before/after):
find <tree> -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256.
[Reconstructed into ~/bh21_work/ after the /tmp sweep destroyed the original
draft; content identical to the pre-sweep draft, from the executor's context.]

RULED BY: §BH20(b) (owner, verbatim in the register): "delete the three stale
C4A outputs (var/ tier, git-ignored), then re-run the two-stage chain under
default environment — no overrides, no --milestone. Declaration first, per
your §BH19(b) discipline: expectations written and sealed before anything
executes, including the :86 FrozenMilestoneWrite stop, which is again the
guard working, not a defect. After the run: the frozen milestone tree
hash-identical, dip0a untouched, worktree clean, HEAD unmoved. If any tracked
file moves, stop and report." Re-affirmed unchanged by §BH21(c): "declaration
sealed before the regen executes, :86 stop expected as the guard working."

THE CODE-PATH FINDING THIS DECLARATION MAKES BEFORE EXECUTION, NOT AFTER
------------------------------------------------------------------------
§BH19(b)'s run observed ONE FrozenMilestoneWrite stop, at run_c4c.py:86,
because its C4a outputs EXISTED and load_c4a() (run_c4b.py:35-46) never took
its regeneration branch. THIS run deletes them, so the branch runs for the
first time — and the branch calls run_c4a.main() (run_c4b.py:40), which has
its OWN milestone writes at run_c4a.py:167 and :192, both through
run_c3b2._write (:207-213), which guards EVERY write with
C.assert_not_frozen_milestone (:209). Read from the code before execution:

  invocation 1 of stage 2 CANNOT reach run_c4c.py:86. It dies INSIDE the
  load_c4a chain at run_c4a.py:167 (writing c4a_family_summary.json to the
  frozen tree), AFTER writing the three fresh c4a outputs to var/ at
  run_c4a.py:141-143. The five c4c views are NOT reached.

  invocation 2 of stage 2 finds the three c4a outputs present (load_c4a
  tests existence — the very staleness mechanism §BH20(a) accepted), loads
  the FRESH data, writes the five c4c views fresh at run_c4c.py:79-83, and
  dies at run_c4c.py:86 — THE RULED :86 STOP, the guard working.

Both stops are the SAME guard (FrozenMilestoneWrite via assert_not_frozen_
milestone, config.py:54-62) refusing the SAME frozen tree. The owner's ":86
stop expected as the guard working" is met at invocation 2; invocation 1's
:167 stop is an ADDITIONAL firing of the same guard at a site §BH19(b) never
exercised. §BH20(c) requires "the fresh views" — reachable under "no
overrides" ONLY by letting stage 2 run to its own :86 stop, which takes the
two invocations above. Declared here, before anything executes: this is the
chain run to completion as ruled, not a retry after a surprise.

THE PROCEDURE (exact commands, cwd = git root, absolute venv python)
--------------------------------------------------------------------
  PY=/Users/symow/Desktop/bbrose-systemOS/bbrose_design_os/venv/bin/python

  DELETE (exactly three files, all proven git-ignored by .gitignore:66 var/
  via git check-ignore -v, rc=0):
    var/design_intelligence/audits/dip0c/c4a/faces.json   (Jul 14 16:16:43)
    var/design_intelligence/audits/dip0c/c4a/files.json   (Jul 14 16:16:44)
    var/design_intelligence/audits/dip0c/c4a/groups.json  (Jul 14 16:16:44)

  STAGE 1:  $PY -m tools.dip0.run          → exit HAND-CAPTURED, expect 0
  STAGE 2A: $PY -m tools.dip0c.run_c4c     → exit HAND-CAPTURED, expect 1
                                             (FrozenMilestoneWrite @ run_c4a.py:167)
  STAGE 2B: $PY -m tools.dip0c.run_c4c     → exit HAND-CAPTURED, expect 1
                                             (FrozenMilestoneWrite @ run_c4c.py:86)

  Environment: default. DIP0C_MILESTONE_OUTPUT unset, DIP0C_ALLOW_MILESTONE_
  WRITE unset, no --milestone flag anywhere. Verified unset immediately
  before stage 1 (env | grep DIP0C → empty).

EXPECTATIONS (declared before execution; scored in the final report)
--------------------------------------------------------------------
E1. Stage 1 exit 0; inventory artifacts under var/design_intelligence/audits/
    dip0/inventory/ (inventory.jsonl, inventory.csv, excluded_junk.json,
    symlinks.json) rewritten with fresh mtimes; row counts REPRODUCE the
    16:02:19 regen the corpus has not moved since: total rows 7590, FONT
    rows 4886 (the pass-1 fresh measurement). materials/ untouched
    (read-only source).
E2. Stage 2A: prints "C4a output missing — running it first..." then
    "auditing 4886 font files"; writes the three c4a outputs FRESH
    (run_c4a.py:141-143, new mtimes replacing Jul 14); traceback ends in
    FrozenMilestoneWrite naming c4a_family_summary.json; exit 1. The five
    c4c views still carry their Aug 31 16:02:51 mtimes (untouched by 2A).
E3. Stage 2B: NO "C4a output missing" line (the three files exist); the five
    c4c views (face_manifest.json, technical_view.json, rights_view.json,
    queues.json, styles.json) rewritten FRESH at run_c4c.py:79-83 (new
    mtimes); traceback ends in FrozenMilestoneWrite naming
    font_review_queue_summary.json — the :86 stop as ruled; exit 1.
E4. DIRECTIONAL, exact values reserved to measurement (they are PASS 2's
    and §BH20(c)'s input, not this declaration's claim): faces.json face
    count > 3966; face_manifest.json face count moves with it; the two
    container face sha256s (478c558e…, 1df075a3…) present or absent in the
    fresh manifest is MEASURED at §BH20(c), not asserted here.
E5. After all three stages: frozen milestone tree docs/design_intelligence/
    dip0c hash-identical to the before-hash below (132 tracked / 132 on
    disk, count unchanged); dip0a tree docs/design_intelligence/dip0a
    hash-identical (5 files); `git status --porcelain` over TRACKED paths
    unchanged vs before (var/ is ignored; the only worktree entries remain
    those the transcription-commit state left — measured at seal time
    below); HEAD unmoved (same hash before and after).
E6. Nothing under tools/, apps/, docs/, or either root's tracked tree is
    written by any stage. No queued item is touched: no freshness guard
    lands (§BH20(a) — the existence-test defect is EXERCISED by this run,
    not repaired), no corpus-pin change, no smalls, no OFL reading.
E7. All three exits hand-captured to ~/bh21_work/regen_s1_exit.txt,
    ~/bh21_work/regen_s2a_exit.txt, ~/bh21_work/regen_s2b_exit.txt at the
    command site (echo $? immediately after each), logs to ~/bh21_work/
    regen_s1.log, regen_s2a.log, regen_s2b.log. The wrapper's status line
    is NOT trusted (four lies on record), and /tmp is NOT trusted either
    (the sweep recorded at §BH21(h)).

HARD-STOP MAP FOR THIS STEP (from §BH21's list, read before it is needed)
-------------------------------------------------------------------------
  · any TRACKED file moves at any stage → stop and report (owner's own
    sentence in §BH20(b)).
  · stage 1 exits non-zero, or either stage-2 invocation stops anywhere
    OTHER than the two declared guard sites → a declaration miss that
    changes what the next step should do → stop and report.
  · frozen-tree or dip0a hash moves → stop and report.
  · faces count NOT > 3966 (E4 directional) → the widening did not reach
    the face set; §BH20(c)'s premise fails → stop and report.

SEAL — measured immediately before execution
--------------------------------------------
  sealed_utc:            2026-08-31T09:33:52Z
  HEAD at seal:          a06ccf6 (the just-landed transcription commit)
  frozen tree before:    36f08a31ad581c3b   (132 tracked / 132 on disk — the
                         §BH19(g) count reproduced exactly)
  dip0a tree before:     2e339a7e23a46c00   (5 tracked / 5 on disk)
  tracked worktree:      `git status --porcelain` EMPTY — fully clean
  env check:             env | grep -c DIP0C = 0 (no overrides present)
