# §BH21 FINAL REPORT — 2026-08-31 — RUN STOPPED AT THE PASS-2 GATE, EARLY UNDER THE GOAL'S OWN HARD-STOP PROVISION

**Verdict line first: 4 of 6 steps EXECUTED AND SCORED, ALL MATCH. The pass-2
gate REFUSED on two failures OUTSIDE the cleared set; hard stops #2, #3 and #4
fired; the run stopped with nothing reverted and nothing destroyed. One
decision no ruling covers is REPORTED below, NOT RESOLVED.** §BH21: *"HARD
STOPS — the only reasons to report early."* This is that report — the one
report, everything scored.

HEAD: **a06ccf6, unmoved** since the transcription. Hand-captured gate exit:
**1** (`~/bh21_work/p2_exit.txt`). Neither landing confirmation obtained
(no exit 0, no new HEAD) — pass 2 is NOT landed, and is treated as such.

---

## 1. THE REFUSAL, MEASURED

Gate run (FORM 3, default env), log `~/bh21_work/p2_gate.log`, verbatim:

```
UNREGISTERED: apps/intelligence/test_manifest_import.py::test_frozen_production_manifest_persists_exact_bounded_corpus_or_fails_closed
UNREGISTERED: tools/dip0c/tests/test_c4b.py::test_the_real_corpus_suspicion_totals_hold
TIER_2=REFUSE collected=8490 failures=2 apps=7684 dip0c=671 dip0=135
GUARDED_COMMIT_REFUSED: TIER_2=REFUSE (A326/3m)
```

Collection identical to every green run (8490/7684/671/135). Both failures
are outside {test_c4c:267, test_c4c:268, test_c5:307} — the set pass 2
existed to clear (all three of mine now pass; the gate's refusal is not
about them).

**Hard stops adjudicated:**
- **#2 FIRED** — *"the gate refuses on anything OTHER than the constants
  pass 2 exists to clear."* Both failures are other things.
- **#3 FIRED** — *"any decision arises that no ruling covers"* — the dip1b
  question, §4 below.
- **#4 FIRED** — *"a prediction misses on a leg that changes what the next
  step should do"* — pred_p2 L6 predicted GREEN/failures=0; the queue record
  cannot follow a refused pass 2.
- #1 did NOT fire — no tracked file moved outside a declared commit at any
  point (porcelain proof in §7).

pred_p2 L6's own sentence pre-adjudicated this: *"A refusal on ANYTHING other
than these three constants = hard stop."* The prediction was honored by
stopping.

## 2. GATE-FOUND MOVER A — test_c4b.py:481-482 (in-mandate, NOT landed)

`test_the_real_corpus_suspicion_totals_hold` pins the c4b suspicion Counter.
Measured fresh through the test's own accessor (`run_c4b.audit()`,
`~/bh21_work/manifest_audit.json`):

| outcome | pinned | measured |
|---|---|---|
| SUSPECTED_SYSTEM_FONT_COPY (:481) | 706 | **706 — HELD** |
| SYSTEM_FONT_EVIDENCE_PRESENT (:482) | 127 | **130 — MOVED** |
| NO_SYSTEM_FONT_EVIDENCE (unpinned) | — | 3133 |

Sum 3969 = the fresh face count; the +3 regen delta sits entirely in
SYSTEM_FONT_EVIDENCE_PRESENT. This IS §BH21(d)'s mandate by its own words —
*"whatever the regen actually moves, by measurement"* — and 130 is measured
true, so writing it would honor *"no constant is ever written to a value not
yet measured true."* It is NOT written: it was outside the sealed pred_p2
write set (§BH4(l) staged==declared), a corrected declaration would be
required, and no declaration can land while Mover B refuses the suite.

**The owned miss:** I enumerated the pin universe as the 13 previously
inventoried pins (test_c4a ×4, test_c4c ×6, test_c5 ×3). The true universe is
every suite assertion that reads regen-refreshed `var/` artifacts —
test_c4b:481-482 and the dip1b sha pins were in it. The gate is the correct
enumerator; my pre-gate measurement was not. This is pred_p2's only
substantive miss (L6, C3), scored in §5.

## 3. GATE-FOUND MOVER B — the dip1b evidence-integrity chain (unruled)

`docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json` — a frozen,
TRACKED production manifest (landed cef40f1; file mtime 2026-07-16 13:00:33,
untouched — porcelain empty over it). It declares **100 sources, each with a
pinned sha256**. Read-only audit (`~/bh21_work/manifest_audit.py`, mtime +
observed-sha for all 100): **45 MATCH, 55 MISMATCH**, exactly two mismatching
paths:

| entries | dataset | pinned path | mismatch since | mover |
|---|---|---|---|---|
| 44–77 (×34) | dip0c4_curated_starter_candidates/1.0 | var/…/dip0c/c4c/face_manifest.json | mtime 17:35:16 today | **the ruled §BH20(b) regen** — sole mover; both green gates this session (fedfab7, a06ccf6) prove the pre-regen 3,966-row bytes hashed to the pin |
| 78–98 (×21) | dip0c3_brand_candidates/1.0 | var/…/dip0c/c3a/brand_candidates.json | mtime 2026-07-16 — **pre-existing**, not this session's work | unknown, ≥Jul 16 |

(The ~20 c2b candidate sources were rewritten byte-identical DURING the
refused run by the suite itself and still MATCH — deterministic, no
divergence. pilot ×10, review ×14, palette ×1 MATCH.)

**Failure mechanism** (test_manifest_import.py:252-268): the integrity policy
was ALREADY `blocks_evidence_dependent_claims` at both green gates — the 21
brand mismatches predate this session — and the fail-closed branch PASSED
because `integrity.unresolved_source_versions[0]` and `prepare_manifest`'s
ManifestError named the same first-unresolved entry, whose expected+observed
shas the test asserts into the message (:261-:262). The regen added a second
mismatch population (entries 44–77) ahead of the brand entries; the
first-unresolved identity between the resolver's list and the error rendering
diverged, and :261's containment assertion measured False. **The test's
fail-closed posture is working as designed** — it detected that a frozen
evidence contract no longer matches the corpus it froze.

## 4. THE UNRULED DECISION — REPORTED, NOT RESOLVED

The ruled regen falsified 34 sha pins inside a frozen, owner-committed
production evidence contract. Every path forward is authority-bearing and no
ruling covers any of them:

1. **Machine re-pins the 34 face_manifest shas** in the tracked dip1b
   manifest → restores the exact pre-regen test behavior (fail-closed branch,
   brand entry first again; the 21 brand mismatches remain and keep the
   passing branch unreachable). But this is a machine edit to a frozen
   production evidence contract — the direct sibling of the QUEUED,
   owner-gated corpus-pin-architecture item.
2. **Edit the test's fail-closed logic** (:252-268 first-unresolved
   assumption) → structural test change, outside every mandate ever issued.
3. **Restore a 3,966-row face_manifest** to satisfy the pin → un-does the
   ruled regen's corpus movement and silences a correct detection; violates
   §BH21(a) directly.
4. **Defer** — leave the refusal standing until ruled. This stop takes
   option 4 by default, choosing nothing.

*"If I meant something narrower, my sentence governs."* — the sentence is
awaited. Note the blockage is total: the gate runs the full suite for EVERY
commit, so the corrected pass 2, the §BH20(d)/§BH21(e) queue record, and any
docs commit are ALL refused until dip1b turns green — the same logic §BH21's
own header used (*"the register cannot land through a refusing gate"*). Once
dip1b is ruled, the remainder is mechanical: corrected pass 2 (4 constants,
all measured true), queue record, final green gate.

## 5. SCORECARDS — EVERYTHING SCORED

**Pass 1 (fedfab7)** — 8 legs, ALL MATCH. Constants 4883→4886, 3941→3944,
47→48; gate GREEN; ledger folded; predictions in
`~/bh21_work/pred_p1_reconstructed.txt`.

**Transcription (a06ccf6)** — ALL MATCH. Pure append to the register;
gate GREEN; `pred_tr.txt`.

**§BH20(b) regen** — declaration sealed 09:33:52Z BEFORE execution
(`regen_decl.md`), E1–E7 ALL MATCH: stage 1 exit 0; stage 2A exit 1 @
run_c4a.py:167 (declared — the code path §BH19(b) never exercised); stage 2B
exit 1 @ run_c4c.py:86 — **the ruled :86 stop, measured**; frozen trees
hash-identical before/after (dip0c `36f08a31ad581c3b` ×132, dip0a
`2e339a7e23a46c00` ×5); porcelain empty; HEAD unmoved; faces 3,966→3,969 with
both container faces present for the first time.

**§BH20(c) join measurement** — read-only (`join_measure.py`, exit 0
hand-captured; 91-file write-control clean). Both faces JOINED
(NotoSans-Regular/face-327979ef355ce8ccd570, NotoSans-Bold/
face-ac29d83abf6138679264); confirmed_fonts +2 at {MACHINE_DERIVED,
LICENCE_REVIEW_REQUIRED}. §BH17(b) Q4 table: **every row MATCH, zero
divergences**; FONT_IDENTITY_MISMATCH did NOT fire; licence fields all
empty; all_production_verified False. *"The entire measured yield is that one
gate code changes its name"* survives execution verbatim. The OFL was not
read (§BH12(a)).

**Pass-2 pre-gate measurement** (`pass2_measure.py`, exit 0, 519-file
write-control clean) — 13 pins through the tests' own accessors: movers 3
(faces 3969, groups 2834, FONT_FACE 3969 — equal to the owner's expected
list, scored as agreement), holders 10, info guards OK.

**pred_p2 (the refused commit), leg by leg:**

| leg | predicted | measured | score |
|---|---|---|---|
| L1 write set | 2 staged files + gate ledger line + 3 captures | exactly that (captures triplet 20260831T095624Z_a06ccf6*) | MATCH |
| L2 diff shape | +2−2 / +1−1 staged | exactly that | MATCH |
| L3 manifest/A391 | no new file | none | MATCH |
| L4 §BH4(l) | staged==declared; one column-2 ledger row; no ?? | porcelain shows exactly the predicted shape | MATCH |
| L5 commit contents | one constants-only commit | **no commit occurred** | NOT REACHED |
| L6 suite | GREEN, failures=0 | **REFUSE, failures=2** (collection numbers all matched) | **MISS — the redirecting miss** |
| L7 ledger | 422 folds into commit, clean after, no orphan | 422 on disk as **orphan** (append happened; fold did not) | append MATCH / fold MISS by consequence of L6 |
| L8 protocol identities | empty diff a06ccf6→new HEAD over the protocol file | no new HEAD exists; substitute: staged diff touches zero apps/ paths | intent PROVEN by substitute |

**Claims:** C1 HOLDS (every written value measured true; still true).
C2 HOLDS (measured set governed; PRG/dual-control untouched). **C3 MISS** —
"leaves nothing currently-false unfixed / ZERO contradicted pins" was false:
test_c4b:482 was currently-false outside my 13-pin universe (the blind spot
owned in §2). C4 HOLDS (no commit; nothing beyond index+ledger would have
been committed). C5 HOLDS (two-sided guard untouched). C6 HOLDS (exit 1
hand-captured; two-confirmation rule correctly classifies pass 2 as NOT
landed).

## 6. GOAL STATE, LEG BY LEG

| §BH21 goal-state leg | outcome |
|---|---|
| gate GREEN at final HEAD | **NOT ACHIEVED** — REFUSE at a06ccf6 |
| worktree clean | **NOT ACHIEVED** — staged pair + orphan, deliberately preserved |
| every commit landed with §AD0(a) declared before, scored after | **ACHIEVED for both landed commits** (fedfab7, a06ccf6 — all legs MATCH); the refused third has its prediction declared AND scored (above); no bar lowered |
| §BH20(c) join measurement recorded in the queue | measurement EXECUTED and SCORED (zero divergences); **queue record NOT LANDED** — draft at `queue_block.md` carries an unresolvable `__P2HASH__` and nothing lands through a refusing gate |

## 7. REPO STATE — NOTHING REVERTED, NOTHING DESTROYED

```
 M bbrose_design_os/docs/roadmap/palt_m6/record_gate_ledger.jsonl   (gate-written orphan, 422 on disk / 421 committed, utc 09:44:43Z)
M  tools/dip0c/tests/test_c4c.py                                    (staged, +2−2, measured-true constants)
M  tools/dip0c/tests/test_c5.py                                     (staged, +1−1, measured-true constant)
```

HEAD a06ccf6. No other tracked path moved at any point (hard stop #1 never
fired). Frozen milestone trees intact (porcelain empty over
docs/design_intelligence/**; hashes re-verified at regen scoring). Captures
triplet from the refused run retained in `.tier2_captures` (gitignored).
Queued items untouched: load_c4a freshness guard, corpus-pin architecture,
the smalls, the OFL reading (§BH12(a) — owner's alone). C3 container stage
untouched and still BLOCKING by construction.

## 8. EVIDENCE INVENTORY — ~/bh21_work/ (durable, outside both roots)

regen_decl.md · regen_s1/s2a/s2b logs+exits · pred_p1_reconstructed.txt ·
pred_tr.txt · tr_gate.log/tr_exit.txt · bh21_block.md · join_measure.py/.err
· join_measurement.json · join_exit.txt(0) · pass2_measure.py/.err ·
pass2_measurement.json · pass2_exit.txt(0) · pred_p2.txt (sealed before the
gate) · p2_gate.log · p2_exit.txt(1) · manifest_audit.py/.json/.err ·
queue_block.md (draft, cannot land as drafted) · this report.

**WHAT IS ASKED FOR: one ruling on §4. Everything else is either scored,
queued as previously ruled, or mechanical once the gate can go green.**
