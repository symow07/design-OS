# §BH23 ONE-REPORT — THE EXTENSION RULED, THE SEQUENCE RUN TO COMPLETION
COMPLETE 2026-09-01 — drafted during gate C, filled as each gate landed;
no scored line revised after its gate. Durable in ~/bh21_work/.

## 0. WHAT WAS RULED AND WHAT RAN

§BH22 stopped at its own hard stop: the (a) amendment's first gate REFUSED
(TIER_2=REFUSE failures=4, exit 1 hand-captured, a_exit.txt) on the
registry root-of-trust pin — beyond the two known movers, so I stopped and
reported (bh22_report.md). §BH23 (typed by the owner, this session) ruled
the one-field extension and ordered the remainder run to completion, one
report at the end. This is that report.

The sequence, as §BH23(b) ordered it:
  A′ (34 pins + 1 registry field, same commit, two authorities)
  → C (transcription §BH22 + §BH23, pure append)
  → B (corrected pass 2, four constants)
  → D (queue record, placeholders resolved; its gate proves the goal state)

Mid-sequence, gate C's first attempt refused on two registered-at-zero
infrastructure flakes (§2); OWNER RULING §BH24 (standing, this arc) ruled
bounded re-runs on exactly that shape and those two ids, its transcription
joined C's append (EXTEND, per its header's first option), and the
remainder resumed unchanged under §BH23(b) per §BH24(c).

## 1. COMMIT A′ — 00ab549 — SCORED AGAINST pred_a2: ZERO MISSES

Gate: TIER_2=GREEN collected=8490 failures=0 apps=7684 dip0c=671 dip0=135,
exit 0 hand-captured (a2_exit.txt); HEAD a06ccf6 → 00ab549 (parent proved
a06ccf6). Both landing confirmations present.

Every leg matched the sealed prediction (pred_a2.txt):
  L1/L2  manifest +34−34 · registry +1−1 · ledger +3−0 = +38−35, 3 files —
         EXACT, including the gate folding BOTH orphans (+3).
  L4     porcelain after landing = exactly the three tools/dip0c test rows.
  L6     the GREEN line, verbatim as predicted.
  L7     ledger 424 on disk == 424 committed, CLEAN — first clean ledger
         since the pass-2 refusal.
  L8     git diff a06ccf6 00ab549 -- bbrose_design_os/apps/ = EMPTY (0 lines).
  C1     both written values fresh-measured at write time (the 34 from
         bh22_measurement.json minutes before; the field matched against a
         same-minute re-hash) — neither taken from a report.
  C2     both count gates PASS (exactly 34, no 35th; ONE field in ONE file).
  C3     the 21 untouched: changed-line grep for dfccbad2 with --unified=0
         = 0 (the single git-show hit is registry:15 CONTEXT, 3 lines above
         the :18 edit).
  C4     the commit message carries both owner sentences verbatim;
         single-use ×2, spent together, no standing authority.
  C5     the guard is now three-sided and un-weakened: corpus regression →
         dip1b fail-closed + four constants; manifest edit → registry
         root-of-trust check, whose pin now names the currently-sealed bytes.
  C6     exit + log hand-captured (a2_exit.txt, a2_gate.log).

pred_a (the first A attempt) stays as SCORED HISTORY: its gate refused as
its own hard stop, scored leg-by-leg in bh22_report.md; nothing there is
re-litigated here.

## 2. COMMIT C — TRANSCRIPTION — ATTEMPT 1 REFUSED; LANDED AT ATTEMPT 2 UNDER §BH24 (2bc229b)

Prepared and verified pre-gate: block 230 lines, 5× placeholder → 00ab549
(0 left), §BH22(c)'s __P2HASH__ kept LITERAL (verified against the
transcript: the owner's own token, typed in the ruling — resolving it
would alter owner text); register append +230 −0, HEAD 16,494-line prefix
byte-identical (diff rc=0); staged == declared both halves; pred_c sealed
before git add.

ATTEMPT 1 REFUSED: TIER_2=REFUSE failures=2, exit 1 hand-captured
(c_exit.txt) — the two REGISTERED_AT_ZERO ConfirmationDialogBrowserTests,
ONE root cause measured from the capture (flush-TRUNCATE deadlock, then
the dirty-DB UniqueViolation cascade). NON-movers → §BH23's first and
fifth stops fired; stopped and reported (c_stop_report.md). pred_c scored
honestly: L1-L4/C1-C3 HELD, L6 MISS, L5/L8/C4 not reached. HEAD unmoved,
index intact, one ledger orphan (mine, stays).
CONTINUATION UNDER RULING: §BH24 (standing, typed this session) ruled
bounded re-runs on exactly the two ids' infrastructure refusals — three
attempts per commit, refused-attempt orphans fold counted, relief state
untouched (A191) — and offered the transcription two homes. EXTEND was
taken, stated here per the header: the §BH24 block (65 lines) joined the
staged append and the invariants were re-proved against HEAD (numstat
295 −0; 16,494-line prefix rc=0; tokens __AXHASH__ 0, owner's __P2HASH__
exactly 1). pred_c2 sealed before re-staging; c_msg updated to three
rulings. ATTEMPT 2 GREEN and LANDED: 2bc229b (parent proved 00ab549),
exit 0 hand-captured (c2_exit.txt), the L6 line verbatim, +297 −0 across
2 files (register 295, ledger 2 — attempt 1's orphan folded per §BH24(a)),
ledger CLEAN 426 == 426, porcelain = exactly the three B rows, apps/ diff
00ab549→2bc229b EMPTY, landed prefix rc=0 at 16,789 lines. pred_c2: ZERO
MISSES — all eight legs and six claims. Attempt count final: 2 of the
ruled three; the §BH24(a) stop tree was never needed.

## 3. COMMIT B — CORRECTED PASS 2 — LANDED 574324d, ZERO MISSES

Diff re-verified live before sealing: test_c4b.py:482 127→130 ·
test_c4c.py:267 3966→3969 · :268 2832→2834 · test_c5.py:307 3966→3969
(numstat 1-1/2-2/1-1). These edits sat in the worktree through gates A′
and C — measured true by full GREEN gates before their own commit.
SCORE ON LANDING: LANDED 574324d (parent proved 2bc229b), exit 0
hand-captured (b_exit.txt), L6 verbatim GREEN, +5 −4 across 4 files
(tests 1-1/2-2/1-1, ledger +1 −0), ledger CLEAN 427 == 427 from the
measured 426 base (pred_b's L7 re-measured at seal, not assumed),
porcelain EMPTY after landing — the first fully-clean tracked worktree
since the §BH20(b) regen, claim C2 held — apps/ diff 2bc229b→574324d
EMPTY. pred_b: ZERO MISSES (eight legs, three claims; the §BH24(a) tree
carried in L6 was not needed). The suite had measured the four constants
true THREE times unstaged (A′; C attempt 1's dip0c leg; C attempt 2)
before this gate staged that proven set.

## 4. COMMIT D — QUEUE RECORD — LANDED 5fa5275, GOAL STATE MEASURED

Block prepared §BH23-aware (213 lines): the §BH20(b)/(c) record lands
under §BH23(b); the pins section enumerates 4 constants + 34 entries + 1
registry field as THREE gate-out-enumerates-the-sweep instances; the
corpus-pin queue item carries the pin-CHAIN fact; the §BH22(b) item
records the 21 + masking coincidence + the registry-governance facts at
already-measured only.
SCORE ON LANDING (the GOAL STATE gate): LANDED 5fa5275 (parent proved
574324d), exit 0 hand-captured (d_exit.txt), L6 verbatim GREEN, +222 −0
across 2 files (queue 221 −0 — the block grew 213→221 with the §BH24
third-interruption sentence before resolution — ledger +1 −0), ledger
CLEAN 428 == 428 from the measured 427 base, landed queue 12,128 lines
with the 11,907-line prefix rc=0, apps/ diff 574324d→5fa5275 EMPTY,
placeholders resolved pre-seal by one sed pass over the payload only
(00ab549 ×3, 574324d ×2, attempt-2 ×1; verified 0 tokens left, 221 lines
unchanged). pred_d: ZERO MISSES — eight legs, six claims. THE GOAL STATE,
MEASURED AT THIS GATE, ALL FOUR CLAUSES: gate GREEN at final HEAD
5fa5275 · worktree clean (porcelain EMPTY, tracked and untracked) · every
commit predicted-then-scored (pred_a and pred_c kept as refused-attempt
history; pred_a2, pred_c2, pred_b, pred_d zero-miss) · §BH20(c)'s join
measurement landed in the queue (block 1's join/Q4 section).

## 5. THE INSTRUMENT INCIDENT, RECORDED HONESTLY

Two A′ launches were aborted by MY OWN preflight guard misfiring — the
self-match trap in a third costume: the guard's echo LABEL
(`echo "guard: pytest=$PY"`) put the unbracketed word into the wrapper
shell's own command line, so `grep -c '[p]ytest'` counted the wrapper (2
in pipeline form, 1 in snapshot-file form). Forensics with a preserved ps
snapshot (a2_preflight_ps.txt) explained every phantom reading exactly;
dense sampling (6×2s, 150×0.3s) plus ledger/capture controls proved NO
real pytest ever existed. A second, independent abort cause in the same
window was mine too: macOS `wc -l <` emits leading spaces, so the ledger
string-compare failed on "   423". Remedies now in the launcher idiom
(file-form snapshot, sanitized labels, `tr -d ' '`) and in memory. Cost:
two aborted launches, no repo effect, no ledger effect (aborts happened
before the script ran — its log file did not exist, confirming the guard
saw only itself).

Also recorded: sealing pred_c, a global sed for the hash briefly garbled
two meta-lines of the prediction's OWN text (the line describing the
placeholder became self-referential). Caught and reworded BEFORE `git add`
— the seal point pred_c itself declares — with the block payload
untouched. Recorded here because prediction text is evidence and the
near-miss is the lesson: resolve placeholders in payloads by sed, but
never sed a prediction's meta-text.

## 6. HARD STOPS — STATUS

§BH22's stop FIRED (the failures=4 refusal) and was ruled by §BH23 — that
is history, reported in bh22_report.md. Under §BH23's re-scoped stops:
  · refusal beyond the movers these rulings clear — FIRED ONCE, at C
    attempt 1 (this bullet read "NONE (A′ GREEN)" when drafted mid-gate;
    completed honestly here): two registered-at-zero non-movers, stopped
    and reported (c_stop_report.md), ruled by §BH24; C attempt 2, B and D
    all GREEN with no further firing
  · 35th manifest entry / second registry field — NONE (count gates PASS)
  · tracked file moving outside a declared commit — NONE (porcelain
    matched the declared sets at every checkpoint)
  · a decision no ruling covers — NONE (the pred_tr filename collision was
    resolved WITHIN ruling scope: the old file is §BH21 scored evidence,
    left byte-untouched; the new prediction took a new name, pred_c)
  · a prediction miss that changes the next step — FIRED ONCE, with the
    same refusal (this bullet read "NONE (pred_a2 zero-miss)" when drafted
    mid-gate; completed honestly here): pred_c L6 predicted GREEN, REFUSE
    measured — reported, then §BH24(a) pre-ruled the re-run tree so no
    same-shape miss could orphan the sequence; pred_a2, pred_c2, pred_b
    and pred_d all scored zero-miss

## 7. THE QUEUE, THE AUTHORITIES, THE STANDING FACTS

  · FOUR owner-gated items per §BH23: load_c4a staleness · corpus-pin
    architecture (now carrying the pin-CHAIN fact and the third
    gate-out-enumerates-the-sweep instance) · the 21 + masking coincidence
    (§BH22(b)) · the smalls. C3 BLOCKING by construction. OFL UNREAD —
    §BH12(a), the owner's act alone; no licence-bearing field anywhere in
    this sequence is non-empty.
  · Single-use ×2 SPENT: §BH22(a) + §BH23(a) authorize nothing further;
    machines do not edit evidence contracts absent an owner sentence.
  · §BH24 STANDS for this arc: bounded re-runs on infrastructure refusals,
    the TWO named ids only, three attempts per commit, refused-attempt
    orphans fold counted. Used ONCE (gate C, landed at attempt 2). It
    raises no invocations_allowed, touches no register (A191), and is not
    a general re-run licence; the cause stays UNESTABLISHED, and a
    same-cascade firing on a DIFFERENT id is a new queue fact per
    §BH24(b), not a widening.
  · The five lineage/docs seal records and brand_evidence.py:35 still read
    as history, byte-untouched. The 21 still measure MISMATCH at entries
    78–98 — recorded, not investigated, awaiting an owner sentence.

## 8. NOTHING ELSE

No decision was taken that a ruling does not cover; no bar moved after any
gate; nothing beyond the ordered sequence was built or edited.
