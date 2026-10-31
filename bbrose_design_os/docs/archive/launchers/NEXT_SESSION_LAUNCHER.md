# AUTONOMOUS RUN MANDATE — §AE charter, sprint 15 as tranche 1, and the road to 100%

## 2026-08-31 — §BH IS THE ARC THAT RAN LAST, AND IT HAS NO NEXT COMMIT. START BY ASKING, NOT BY BUILDING.

**Read this block before anything below it. Everything under it was written on
2026-08-22 and the sentence "§BA IS THE LIVE TRANCHE" has been false since at
least 2026-08-25** — see the correction two paragraphs down, which is measured
rather than inferred.

**§BH16(c)'s ordered four are all landed:** `2d46f5c` (transcription),
`a76242c` (§BH16(a) inversion), `6ce5e6c` (§BH12(a) producer, capped and
UNWIRED), `9070991` (§BH12(b) BUILD D guard). Each carried an eight-leg
§AD0(a) prediction written before the gate; the guard's eight all matched. Gate
read `TIER_2=GREEN collected=8355 failures=0 apps=7684 dip0c=671`.

**THERE IS NO ORDERED NEXT COMMIT.** §BH16 is the last section in
`OWNER_BLOCKER_CLEARANCE.md` and nothing in it orders anything after the guard.
**Do not pick the next item off the open list and start building it.** The
2026-08-31 block at the end of `OWNER_REVIEW_QUEUE.md` asks the owner for a
ruling on what follows, and that ruling is the input this session needs. If it
has not been given, ask for it — the standing rule is that the owner rules and
the executor measures.

**ONE ITEM ON THE OPEN LIST IS FORBIDDEN TO START, NOT MERELY UNSTARTED:** the
extension of the dip0c audit to `static/fonts` is owner-gated and §BH15(b)
forbids beginning it. The other three §BH16(h) items — the `begin_traced_queue`
namespace guard, the `establishment_table` counts correction, and the
`finding_4` appends blocked on the A391 chain — are open but unordered.

**CORRECTION TO ITEM 8 BELOW, MEASURED 2026-08-31 (§AZ0(u): a claim you wrote
yesterday is not a measurement you have).** Item 8 says Section C carries *"five
BLOCKING rows — C1, C3, C9, C10, C12"*. Read off `OWNER_INPUT_MANIFEST.md`
today, **C12 is RULED (2026-08-25 at §BB2) and is no longer blocking**, and the
fifth blocking row is now **C15** (a 0.312 mm hairline stroke, blocking for the
MOTIFS axis only). The current set is **C1, C3, C9, C10, C15**. C13, C14 and C16
are also ruled since this file was written. The count did not change; one member
did, which is exactly the substitution a stale list hides.

**C3 IS THE ROW THE ENTIRE §BH ARC SITS UNDER, AND IT IS STILL BLOCKING.** C3
reads *"Chosen is not licensed — the gap between those two words is this row."*
The arc did not narrow it and could not: §BH12(a) ruled that *"reading the OFL
is my act, not code's."* What the guard changed is that the gap is now
**enforced** — before `9070991`, a machine could write `VERIFIED_FOR_PRODUCTION`
into a face record and nothing stopped it; measured against the pre-guard tree,
all nine probe cases were stored verbatim with `is_fallback=False`. Closing C3
needs the owner to read a licence.

**TWO SHELL IDIOMS THAT COST THIS ARC REAL TIME. Both are the same class — a
clean exit code is not evidence the query asked the right question.**

* **`${PIPESTATUS[0]}` is ALWAYS EMPTY here.** This is zsh, not bash. The array
  is `pipestatus` and it is **1-indexed**. The bash form renders as `RC=`, which
  reads as "no failure". Twelfth firing. Redirect to a file and read `$?`.
* **There are TWO ROOTS** — the git root (this directory) and the pytest/venv
  root `bbrose_design_os/`. `docs/` and `tools/` are tracked under BOTH, so a
  bare relative path is valid in both and returns different content at exit 0.
  `git show <sha> -- bbrose_design_os/apps/...` run from INSIDE
  `bbrose_design_os` returns **empty at exit 0** — pathspecs resolve
  CWD-relative while `--numstat` and `--porcelain` PRINT root-relative, so
  copying one into the other silently returns nothing. Thirteenth firing, and
  the one that nearly put a false precedent into a commit message.

**WHAT THIS BLOCK DID NOT VERIFY.** The numbered list and every tranche block
below it were not re-audited. Their staleness is established by the register's
own progression — §BB, §BC, §BD, §BE, §BF, §BG and §BH all landed after §BA,
and **§BF closed the §3 question** the last queue block was still pricing — not
by checking each line. Treat any scope sentence below as a claim carrying an
unknown search, per AZ0(t)/AZ0(u), which that text says of itself.

---

**This supersedes the per-sprint launcher. §AD's work items were never
dispatched and are folded in below as tranche 1.**

**§BA IS THE LIVE TRANCHE. C11 IS RULED: THE MOTIF FIELD IS A SURFACE.** Read
`OWNER_BLOCKER_CLEARANCE.md` **§BA** (2026-08-22, OWNER-RULED) before anything
else in this file, and read **BA2 in full before you write the edit** — the
obvious encoding of this ruling is *provably degenerate* and silences every
finding in the module rather than eighteen. The tripwire that catches it
already exists and is named. **And read BA3 before you report the row closed:
SURFACE does not take the front to zero findings, it converts eighteen
clear-space findings into one BACKGROUND finding, which is the new owner row
C12.** The `TRANCHE NOW LIVE — §BA` block is below.

**§AY IS EXECUTED. §AU FOLLOWS §BA, exactly as §AY said it would.** Both §AY
orderings were carried out; AY1 landed at `c470b88` and AY2's code at
`02ff1c9`. **§AY2 did not close its row** — it cleared three of four front
states, and the fourth, which is the state
`targets/container/__init__.py:1081` composes, resolved to AY2's own step 3 and
went to the owner as **C11**, which §BA has now answered. Read `AY-EXECUTED`
below before assuming any part of §AY is still to do.

**AND READ AZ0(t) BEFORE YOU TRUST ANY SCOPE SENTENCE IN THIS FILE.** A
fresh-agent audit of `02ff1c9` found a **false sentence in that commit's WHAT
THIS DOES NOT CLAIM section** — it said production's layout was unchanged, and
production's front had moved **1.5125 mm**. Four more claims in the tranche
share one mechanism with it, and the corrections have been applied to this file
where they touched it. Two of them matter to your work directly:

* **`compose_container_graph` is NOT the composer production usually reaches.**
  `targets/container/__init__.py:1050` routes a confirmed dropper geometry to
  `compose_dropper_sheet`; line 1081 is the `else`. The dropper composer places
  the same mark with **no keep-out at all** (C10).
* **An extent must be scoped by the QUESTION, not by the artefact in hand.**
  Before stating one, ask what a result would have to look like to refute the
  claim, and confirm your search could have produced it.
* **AZ0(u) adds the clause that matters most here: the check applies to your
  own prior writing with no discount.** An extent you recorded yesterday is not
  a measurement you have. It is a claim, and it carries the search that
  produced it — which for the three sentences corrected this tranche was none.

**AND BEFORE YOU OPEN A `## §Ax — EXECUTOR-RULED` SECTION, READ AS2(3).**
It is at `OWNER_BLOCKER_CLEARANCE.md:5354`. **Half the file cites it by the
wrong number**, which is part of why it is walked past: AU8(i) and §AV both
call it *"§AS3's prohibition"*, and §AS3 (5367) is *WHAT THIS DOES NOT CHANGE*
and contains no prohibition at all. §AW (6176) cites it correctly. The text:

> *"You may not open a new `## §Ax — EXECUTOR-RULED` section while the
> preceding tranche moved zero nodes, until either a node has moved or the
> blocking reason is written into `OWNER_INPUT_MANIFEST.md` as a row with my
> name on it."*

**AS2(4) is the only way through and it is narrow:** the section must unblock
a node you are ACTIVELY BUILDING, and you must **name that node in the
section**. §AX3, §AZ and the §AV opening all carry that line — copy the form.

**This bit.** In the tranche that landed `/1.1` I had a §BA drafted and was one
edit from writing it. The preceding three tranches (`b4a1cf9`, `cc3799e`,
`85fac94`) each reported **zero nodes moved**, so AS2(3) barred it, and AS2(4)
did not rescue it: the section would have ruled on the manifest's `reports`
list, and I had already measured that **nothing in the repository reads that
field** — a field no consumer reads cannot be unblocking a node. §AE1 still
decides engineering questions alone; what it does not do is require a clearance
section for each one. **The reasoning went into the code comments and the
commit message, the code shipped, and the section was not written.** §AS exists
because "seven more hours of the same shape ends with forty clearance
sections". That was the shape I was in.

**READ FIRST, IN THIS ORDER:**

1. `OWNER_BLOCKER_CLEARANCE.md` **§BA** — 2026-08-22, OWNER-RULED, **the live
   tranche and the FIRST thing to do**. C11 is answered: the motif field is a
   **SURFACE**. **BA2 carries three bars on the encoding and a witness set of
   three things, no subset of which is reportable.** **BA3 carries the reason
   this does not clear the front.** Neither is optional reading and both are
   load-bearing before the first line of the edit.
2. `OWNER_BLOCKER_CLEARANCE.md` **§AU** — OWNER-RULED, and the tranche after
   §BA. The three rows that stopped VQR-3 are ruled. **Read §AU5 before you
   touch `hierarchy_lines`** — it is the clause that stops this section being a
   licence to draw a fake front, and **§AY did not discharge it.**
   **§AU order 1's steps 1, 2 and 4 ARE BUILT — §AV built them and this line
   used to say "UNBUILT", which was false (AZ0(u)).** The static half is
   `tools/brand_strings.py`, the runtime half is
   `apps/ire/brand_string_runtime.py`, and it is wired at
   `targets/container/__init__.py:1349` and `native_handoff.py:114`/`276`.
   **What remains of that order is step 3 alone: actually supplying
   `hierarchy_lines`** with `text` = the literal `⟪PROVISIONAL⟫` and
   `provisional: true`. Measured: no production path supplies it today.
   **Do not rebuild the guard. Read §AV before you write a line of it.**
3. `OWNER_BLOCKER_CLEARANCE.md` **§AY** — 2026-08-21, OWNER-RULED, **EXECUTED**.
   Do not re-execute it. Read it for the two laws in AY-4, which bind
   permanently and are not tranche-scoped: **§AY0(d)** (an absence carries a
   search extent; a quantity carries the state it was measured in) and
   **§AY0(e)** (a refusal to act is reported at the volume of an action). Both
   were load-bearing in the tranche that executed §AY and both caught a wrong
   claim of mine before it shipped.
4. `OWNER_BLOCKER_CLEARANCE.md` **§AZ0(p)** and **§AZ0(q)** — the two findings
   §AY2 produced on the way past. AZ0(q) is the one that matters: **every
   number in this tranche's rulings was measured on a front the repository
   never composes.** AZ0(q) is the row §BA answers, and **§BA upholds its
   refusal to make the edit unilaterally** — read BA1(c) for why the same edit
   is legitimate now and would not have been then.
5. `OWNER_BLOCKER_CLEARANCE.md` **§AE** — the autonomy charter. Read AE2 before
   AE1: the permission is easy to remember and the limits are the part that
   matters.
6. `OWNER_BLOCKER_CLEARANCE.md` **§AS** — a tranche closing with no node moved
   is a reportable defect. Still in force and it applies to the §AY tranche too.
7. `OWNER_BLOCKER_CLEARANCE.md` **§AD** — sprint 14's rulings. Still in force.
8. `OWNER_INPUT_MANIFEST.md` — everything the machine needs from a human. Rows
   **A10, C2 and now C11 are RULED and no longer blocking**; **C8 is split** —
   its shape is ruled, its string is the new row **C9**. Section C now carries
   **five BLOCKING rows — C1, C3, C9, C10, C12** (counted in this revision of
   the file, per §AY0(d); C2, C8 and C11 are ruled and C4–C7 are CEILING).
   **C12 is new and §BA created it by answering C11** — it is the background
   axis the SURFACE ruling moved the question onto, and it is the reason the
   count did not drop. C10 is the dropper front's mark at **8.8000 mm** against
   C2's **12.0 mm** floor. None of these is an arithmetic problem the executor
   may solve by moving a bar. You extend this file. You never fill it in.
9. The §BA, §AY, §AU, §AS, §AE and §AD ANSWERED blocks at the end of
   `OWNER_REVIEW_QUEUE.md`, and the **§AY EXECUTED** block appended after them.

---

## A12 IS SATISFIED. THE GUARD'S PRECONDITION IS TRUE. THAT IS NOT THE SAME AS THE GUARD FIRING.

**Owner action, 2026-08-22, verified.** `ENVIRONMENT=LOCAL_DEVELOPMENT` is in
`bbrose_design_os/.env` — exactly one assignment matching `^ *ENVIRONMENT *=`,
at line 19, with that value, and no second assignment to override it. Extent:
that file only; CI is deliberately still unset and must stay that way.

**`ops.migration_guard` does not close on this.** §AA: a guard nobody has seen
fire is not evidence of anything. The row's "remaining 40%" was bought by the
*input*, not the *result*. The result is a measurement someone still has to
take: run the thing, and report whether
`check_standard_pipeline_activation`'s migration arm actually names
**`dielines.0008_alter_dielinejob_template_type_and_more`**. **Report it at the
same volume if it stays silent** (§AE0(e)) — a third lock nobody has found yet
is a live possibility and finding it is worth more than the close.

**Do not go looking in §BA for this.** A12 was filed annotated *"new at §BA"*
before §BA existed; the §BA that was written rules on C11 and contains no
environment ruling. The correction is in the A12 row and in the SATISFIED block
at the end of `OWNER_REVIEW_QUEUE.md`. **A11 — the empty `ANTHROPIC_API_KEY`
export in the same file — is untouched and still BLOCKING.**

---

## TRANCHE NOW LIVE — §BA. THE MOTIF IS A SURFACE. ENCODE IT WITHOUT BREAKING THE DETECTOR.

**Authority: `OWNER_BLOCKER_CLEARANCE.md` §BA, 2026-08-22, OWNER-RULED.**
C11 is answered. The four steps below are the tranche. **The order is fixed
and is not yours to reorder** — the same discipline §AY1 used, and for the
same reason.

**AS2(4) compliance — the node this unblocks, named:**
`pc.vqr3_artwork_composition`. The front the live composer emits carries
eighteen clear-space findings that no layout change can clear; until the
category question is encoded, the artwork axis cannot be measured on the state
production actually composes.

### BA-1 — READ BA2 AND BA3 BEFORE YOU WRITE ANYTHING

Not a formality. **BA2(c) proves the obvious encoding is degenerate.**
`_ink_box` returns `None` for a group, so a field's box has to be computed as
the union of its descendants'; the union of a set of boxes contains every
member; the mark is a descendant of `Root`; therefore **`Root`'s box contains
the mark unconditionally.** A rule reading *"inherit the exclusion from any
ancestor whose box contains the mark"* does not take eighteen findings to
zero. It takes **every** finding, on every front, to zero, forever.

**BA3 is the other half:** ruling the motif a ground moves the mark onto the
**background** axis, where `BACKGROUNDS_PERMITTED` is
`("brand_light_ground", "pure_white")` and everything else emits
`CODE_BACKGROUND_FORBIDDEN`. **Eighteen clear-space findings become one
background finding, and it is a red.** That is expected, it is filed as owner
row **C12**, and it is not yours to make green.

### BA-2 — ENCODE THE EXCLUSION, TWO CONDITIONS, BOTH REQUIRED

A node inherits the ground exclusion only when **(1)** it is a member of a
field **declared** a decoration ground — a role carried at composition, not a
name matched at validation — **and (2)** that field's box contains the mark's
box entirely.

**The declared role already exists and you do not need to add it.**
`apps/ire/compose_container.py:186` constructs the field as
`Group(name=name or f"motif-{role}", role="decoration", children=nodes)`.
*(This settles §BA's own bet BA5(a), which §BA called the one most likely to
be lost. It was measured after §BA was signed, which is why it is recorded
here and in C12 rather than inside the signed section.)*

**BA2(b) is the clause that will bite you: MEMBERSHIP, NEVER COORDINATES.** A
text run drawn on top of a motif field is still a neighbour. It is not made
into a surface by sharing a bounding box with one. If the exclusion propagates
by coordinates, §AY2's text keep-out at `02ff1c9` becomes unmeasurable and the
1.5124 mm collision §AY0(b) pinned could come back with no finding to name it.

### BA-3 — PROVE IT WITH THE WITNESS SET. THREE THINGS. NO SUBSET IS REPORTABLE.

1. the eighteen motif findings on `_live_front()` go to **zero**;
2. `test_a_field_that_only_OVERLAPS_the_logo_still_is_one`
   (`apps/ire/tests/test_au3_brand_usage.py:795`) **still reports its
   violation**. Its `decoration-field` is a direct child of `Root`, which is
   precisely why it catches the degenerate encoding. **It may not be edited,
   relaxed, or parametrised to accommodate this ruling.**
3. a **text node** inside the motif field's box on that same front is **still
   reported**. If none exists to measure, compose one in a test rather than
   asserting the property in a docstring — §AY0(d).

**If (1) holds and (2) or (3) does not, the exclusion became universal, the
edit is a detector tuned to pass, and you report it as that and revert it.**
Reporting (1) alone as success is the failure mode this tranche exists to
avoid.

**Tests encoding the pre-ruling state are INVERTED, not deleted** — lines 335
and 341 and the class docstring at 300, per BA2(d), with the docstrings
recording why they once failed left standing. Same handling
`test_the_front_the_repository_emits_today_FAILS_this_gate` got at §AY2/AZ5.

### BA-4 — DECLARE THE BACKGROUND TRUTHFULLY AND COMMIT THE RED

Once the motif is a ground, `background="pure_white"` is a **false**
declaration of the state being measured. Change it to the truthful one and
commit whatever the instrument says.

**You may not pre-empt C12 in either direction (BA3(d)).** You may not add
`motif` to `BACKGROUNDS_PERMITTED`. You may not switch `background=` to
something that passes. **You may not switch it to `None`** — `None` reports
UNMEASURED, and choosing UNMEASURED to dodge a red is choosing the answer most
likely to be green, which `evaluate_brand_usage`'s own docstring forbids in
those words. **If the truthful declaration produces
`CODE_BACKGROUND_FORBIDDEN`, commit the red and report it at the volume of a
success (§AE0(e)).**

**What would actually help the owner answer C12:** a rendered comparison at
true scale — the mark on the motif front as composed, beside the mark on plain
white, at the size it prints. That is a legitimate deliverable of this tranche
and it is not a §AE2(c) decision to produce one.

### WHAT THIS TRANCHE DOES NOT DO

**It does not touch C10** — the dropper composer, the SIZE axis, still the
owner's. **It does not supply C9 and does not discharge §AU5**; note that
§AU5's step 1 is BUILT (`tools/brand_strings.py`,
`apps/ire/brand_string_runtime.py`, wired at three call sites) and must not be
rebuilt. **It advances no acceptance gate** — `owner_acceptance` is
untouchable under §AE0(a). **It moves no bar** — not the 1.0× cap-height clear
space, not the 12.0 mm floor, not `BACKGROUNDS_PERMITTED`. **§AS2(2) binds**: a
tranche closing with no percentage moved is a reportable defect, reported
first.

---

## DECLARED EXECUTOR WORK, CARRIED OUT OF §AY — THE RECORD GATE'S EXTENT

**§AZ0(m). This is not an owner ask; nothing here needs a decision.** The
record-integrity gate declares `RECORD_ROOTS = ("docs/roadmap",)` and quotes
that root back in its own refusal messages, but its binding `PATTERNS` cover
`docs/roadmap/palt_m6/**` only. Measured 2026-08-21:

```
DECLARED ROOT   docs/roadmap           1,947 json/jsonl
ACTUALLY BOUND  docs/roadmap/palt_m6   1,735
UNPROTECTED, inside the declared root    212
```

The 212 include **`progress_tracker.json`** — all 106 nodes, the file this
programme reads to know what is done — plus `master_roadmap_v3.json` and
`acceptance/product_container_acceptance_rejection.json`. `records=1734
failing=0` is true and reads as coverage of the declared root, which it is
not. `classify_complement` exists to catch a RECORD_KIND outside the binding
pattern and walks the *narrow* path itself, so it cannot see them.

**Why it was not fixed in §AY:** widening the pattern admits 212 records at
once and will mint refusals across all of them, inside a tranche whose subject
was a network guard and a clear-space collision (§AC). **Do it as its own
tranche**, expect the first `--regenerate` to be large, and check under
§AR4(1) that the diff is additive before applying it.

**While you are in there:** `tier2_gate.py --regenerate-manifest` is a WRITE,
not a query — it stamps `generated` with the wall clock, so a run reporting
`added (0) / removed (0)` still moves the digest and still costs a rebind, an
identity recompute and a re-pin. Run it only when a test file actually moved.
That is §AZ0(l), and it cost this tranche a full chain pass.

## ALSO CARRIED — THE SUITE OVERWRITES THE COMMIT PATH'S OWN EVIDENCE FILE

`GuardedCommitTests` in `apps/pipeline/tests/test_palette_statistics.py` runs
`tools/guarded_commit.sh --dry-run` three times with `cwd=os.getcwd()`, so the
nested script writes the REPOSITORY'S real `.suite_gate_result`, and one of
the three reads that shared file back to assert on it.

**Why you care:** on a run the gate REFUSES, `guarded_commit.sh` exits at line
212 and never reaches the honest artifact rewrite at line 219 — so what is
left on disk is a TEST'S red result (`"cmd": "false"`), not the run's. That is
exactly when somebody is reading it to find out what went wrong. Measured with
a sentinel, not inferred; §AZ0(o) carries the transcript.

**Bounded:** it cannot corrupt a commit decision — the artifact is written at
line 125 and read back at line 128, before TIER_2 runs at line 206 — and the
file is gitignored, so nothing wrong is ever committed. Diagnosis only. But
diagnosis is the only thing that file is for.

**Not a one-liner.** The script resolves `venv/`, `tools/` and the record
roots relative to its cwd, so giving the nested runs a directory of their own
is real engineering. Do it alongside the §AZ0(m) work above, or in its own
tranche. PRE-EXISTING (the A137 tests long predate §AY); found there, caused
elsewhere.

## ~~ALSO CARRIED — THE MANIFEST STILL SAYS 1.0 AND THE FRONT IT DESCRIBES MOVED~~ — DONE, AND EVERY REASON THIS SECTION GAVE WAS FALSE

**The bump landed. Not one sentence below was a reason for it — and a correct
reason existed the whole time, one section away, in the ruling that ordered
the bump.** §AW4 item 4 (`clearance:6458`) measured it: `/1.0` had *"gained the
key `artefact_withheld`, and `concept_sheet_ai` / `preview_png` went from
always-string to nullable, with **no version bump**"* — an undisclosed schema
change. **Copying the item into this launcher replaced that measured reason
with an invented one**, which then got sharpened twice. §AW4(4) closed with
*"It is taken to `/1.1` in the commit that follows this section"*; **six
commits followed and none did it.** Kept in place rather than deleted because
the way this section got MORE confident across three commits without anyone
opening the file is the finding.

~~`container_native_output_manifest/**1.0**` describes a front that §AY2
changed: three of its four states now place type lower, and where a divider
rule exists it moves with them.~~ **FALSE.** The manifest has eight fields and
**not one of them is geometric**: `schema_version`, `views`,
`artefact_withheld`, `surfaces_with_artwork`, `technical_only_surfaces`,
`records_on_sheet`, `records_on_sheet_extent`, `legacy_raster_preserved`. It
cannot describe a front. `git show --stat 02ff1c9` — the commit that moved the
front — touches `compose_container.py`, `container_brand_usage.py`, three test
modules and the ledger, and **does not touch
`targets/container/__init__.py` at all**.

~~*"§AU8(c) applies to the `emitted` flag in it"*~~ **MISATTRIBUTED.** §AU8(c)
(clearance:5944) is about **`container_front_rule.emitted`**, which lives in
`apps/ire/container_line_weight.py:89` and is a different record in a
different file. `grep '"emitted"' targets/container/__init__.py` returns
**nothing** — the manifest has never had such a flag, and neither has the
target.

~~*"the manifest is describing a layout the repository no longer emits, on the
live path"*~~ **ALSO FALSE, AND IT IS THE CORRECTION.** I wrote that in
`cc3799e` while striking the sentence beside it. The strike was right about
the clause it named and repeated the surrounding premise in stronger language,
which is `85fac94`'s own lesson — *a fix inherits the aim of the thing it
fixes* — failing on the paragraph being written at the time.

Provenance, measured with `git log -S`: `b4a1cf9` wrote the section,
`cc3799e` sharpened it, `85fac94` recorded the general lesson and did not
revisit it. **Three commits touched this paragraph and none opened the record
it is about.**

**WHAT WAS ACTUALLY WRONG, and it was found by opening the file.** `/1.0`
carried a hand-written `reports` list of **seven** names against **35** keys
on the sheet. Lines 1406-1414 are eight consecutive report assignments and it
named six — skipping `container_design_graph/2.0` (1406) and
`container_typography_fidelity_report` (1413), **the second of which sits
between two it did name**. `/1.1` replaces it with `records_on_sheet`, derived,
plus `records_on_sheet_extent`. Nothing read `reports`; nothing pinned the
schema string. Three tests and two mutants in
`test_wif_reconstruct_container.py`.

## HOW YOU RUN THE SUITE, AND IT IS NOT OPTIONAL

```
env -u ANTHROPIC_API_KEY tools/guarded_commit.sh -m "$(cat /tmp/msg.txt)"
```

**`env -u` is PER-INVOCATION and the empty export returns every session.** That
is owner ask **A11**, it is still open, and it has now recurred in two
consecutive tranches — predicted in `c470b88`'s message and observed on
schedule in the next one. Without it,
`test_complete_product_creates_project_plus_container_child` fails **409 vs
201** at `complete_product_preflight`'s `provider_configuration` blocker, which
requires both keys non-empty. **Lengths only, per §AY1(d): `ANTHROPIC_API_KEY`
resolves at 0, `OPENAI_API_KEY` at 164.** A red suite from this cause is not a
regression, and reading it as one costs a tranche.

**Three traps recurred while executing §AY and all three are cheap to avoid:**

* **Two roots.** Git root is `/Users/symow/Desktop/bbrose-systemOS`; pytest root
  and `tools/` are one level down in `bbrose_design_os/`. **Bash cwd persists
  between tool calls; shell state does not.** A `cd` you did four calls ago is
  still in effect and a `cd` plus an `export` is not.
* **`| tail` masks the exit code.** `guarded_commit.sh` REFUSED a run and the
  pipeline reported success, because the exit status belongs to `tail`. Redirect
  to a file and echo `$?` on its own. That is A315/1q and the script's own
  header warns about it.
* **Never override `SUITE_CMD`.** The script refuses without
  `EXTENT_ASSERTION_OPT_OUT=1`, and **it is right to.** With the opt-out the
  extent assertion is skipped AND TIER_2 becomes `NOT_RUN_SUITE_CMD_OVERRIDDEN`
  — i.e. the full suite never runs. That combination is the `ad3db82` bypass
  §AY1 declared an **UNEXCUSED DEFECT**. It has no remaining justification here.

---

## AY-EXECUTED — §AY. THE CREDENTIAL, THEN THE CLEAR SPACE. WHAT LANDED.

**THIS BLOCK NO LONGER DISPATCHES WORK. It is kept whole because it carries the
corrected numbers, and because the ordering it gave is the reason the outcome
below is reportable rather than embarrassing.** §AU is now first. Its block is
below and its ordering was never touched.

```
AY-1  the credential          DONE      c470b88, all four steps, in order
AY-2  the clear space         DONE      02ff1c9, and it did NOT close the row
          state 1  no hierarchy, no motif            1 -> 0 findings
          state 2  MOTIF FIELD, no hierarchy  LIVE  19 -> 18   <-- see below
          state 3  hierarchy + motif                 2 -> 0
          state 4  hierarchy, no motif                1 -> 0
AY-3  what §AY does not unblock          STILL TRUE, all of it
AY-4  the two new laws                   IN FORCE, permanently
```

**THE PART THAT COULD NOT BE DONE, AND WHY YOU MUST NOT RETRY IT BLIND.** State
2 is the only state the two production call sites compose. In it the mark sits
on a rendered motif field whose every strand runs 68.5240 → 102.4160 mm,
straight through the mark's clear band at 67.4929 → 77.2674. **18 findings, 14
of them `gaps_mm {'overlapping': 0.0}` — which is not a margin encroachment, it
means the strand crosses the mark's own box.** AY2 step 1 is unavailable (the
strands have no independent vertical position; moving one runs its bottom off
the floor of its own zone) and **step 2 is unavailable for a stronger reason
than AZ5's 62.3 % arithmetic** — 14 of the 18 overlap the mark itself, so no
size reduction removes them and the 12.0 mm floor is not what stops this. **So
step 3 fired, in AY2's own words, and the question went to the owner as C11.**

**THERE IS A ONE-LINE FIX AND YOU MAY NOT MAKE IT EITHER.** Widening
`_clear_space_findings`' GROUND exclusion so a FIELD of strands counts as a
surface takes 18 findings to 0 in a single edit, and there is a real argument
that a motif field IS the surface the mark sits on. That argument is C11 and it
is the owner's. Making it in the commit whose artwork the detector is refusing
is §AL4, §Y2 and §AU6(c) at once, and the exclusion's own docstring already
says it "cannot quietly grow to cover an inconvenient finding."

Two executor refusals arrived at the owner from opposite ends of the tranche
and both were correct: §AX would not unshadow a live API key because unguarded
spend is §AE7(c), and §AW/§AX would not resolve C2's clear-space failure
because the bars are §AE2(c). **Both are answered in §AY with an ordering, not
a fix.**

### AY-0 — read the corrections before the rulings, because they change the work

**The claim that no `conftest.py` exists anywhere is FALSE.** Four are tracked;
`bbrose_design_os/conftest.py` sits at the pytest root, committed at `80978a6`,
eleven lines, Celery-only. The substance survives — `autouse=True`,
`socket.socket`, `disable_network`, `no_network` and `block_network` across all
four return **zero hits** — but the correct statement is *"four conftests, none
of which blocks an outbound call."* **Consequence: the guard goes INTO the
existing file. Do not create a second root conftest.**

> **STATUS AT HEAD — THE COUNT HOLDS, THE SUBSTANCE DOES NOT.** Four tracked
> conftests: still exactly right (`bbrose_design_os/conftest.py` plus
> `tools/dip0{,b,c}/tests/conftest.py`). **"Eleven lines, Celery-only" and
> "none of which blocks an outbound call" were true when §AY0(a) ruled them
> and are FALSE now** — §AY1 put the guard into that file at `c470b88`. Today:
> **256 lines**, `autouse=True` **4 hits**, `socket.socket` **7 hits**, and it
> carries `OutboundCallRefused` + `_block_outbound_calls`.
> `disable_network`/`no_network`/`block_network` are still **0** — those three
> names were never the guard's names, so their absence measures nothing about
> whether a guard exists, which is why they read as evidence and were not.
> **Do not build this guard. It exists and it has been watched refusing.**

**The collision numbers the owner quoted were the future column.** §AX0(a)
caught it and the owner's question repeated it anyway. Use these:

```
intruder          product-name-0     (NOT rule-front-single — that is the
                                      AFTER state, once hierarchy_lines lands)
gap               1.5737 mm
required          3.0861 mm
shortfall         1.5124 mm
live front        28.80 mm  (label_zone — NOT the 35.00 mm §AU3 assumed)
logo placed at    17.28 mm  (above the 12.0 floor, so size PASSES)
```

**The intruder is a variable.** `product-name-0` today, `rule-front-single`
after C9. A remedy phrased as "move the rule down" does not fix the failure
that exists now.

### AY-1 — the credential. Four steps, in this order, no reordering.

> **ALL FOUR RAN AT `c470b88`. THE OWNER'S ORDERING IS REPRODUCED AS RULED;
> STATUS IS ANNOTATED, NOT REWRITTEN.** Step 3 is the one to read carefully —
> it is done in a way that undoes itself every session.

```
1. BUILD  the outbound-call guard into bbrose_design_os/conftest.py.   DONE
2. WATCH  it refuse a REAL outbound call. Not grepped. RUN. Capture.   DONE
3. CLEAR  the empty ANTHROPIC_API_KEY shell export so .env resolves.   PER-RUN
4. RERUN  the full suite through guarded_commit.sh. No SUITE_CMD.      DONE
```

1. **DONE** — `c470b88`, into the existing file, not a second one.
2. **DONE and it is the reason the first version was thrown away.** `c470b88`
   records the counterfactual established outside pytest first:
   `api.anthropic.com:443` reachable in 0.242 s, then refused under the guard.
   The first version permitted loopback unconditionally and leaked every HTTP
   call through this machine's `HTTPS_PROXY=http://127.0.0.1:3213` **while
   passing its own tests**.
3. **PER-INVOCATION ONLY, AND IT RETURNS.** Measured again this session:
   `ANTHROPIC_API_KEY` is an **empty string** in the shell that runs these
   commands. `c470b88` states it plainly — *"the empty export is gone; no
   shell rc file sets it, `env -u` is per-invocation, and it returns next
   session. That is owner ask A11."* So `env -u ANTHROPIC_API_KEY` stays on
   every `guarded_commit.sh` call, and this step does not get struck.

   > **CORRECTION, 2026-08-22 — `env -u` DOES THE OPPOSITE OF WHAT MY OWN
   > ANNOTATION ONE COMMIT AGO (`4d59a68`) IMPLIED, AND THE TABLE LINE ABOVE
   > WAS RIGHT ALL ALONG.** Line 3 of the block says *"CLEAR the empty
   > `ANTHROPIC_API_KEY` shell export **so .env resolves**"* — that is the
   > mechanism, stated correctly, and I annotated past it.
   >
   > **Controlled comparison, one variable, lengths only per §AY1(d), both
   > from `config.settings` in this session:**
   >
   > | invocation | `os.environ` len | `settings.ANTHROPIC_API_KEY` len |
   > |---|---|---|
   > | plain (empty export present) | 0 | **0** — and `apps.pipeline.apps` logs *"ANTHROPIC_API_KEY is not set"* |
   > | `env -u ANTHROPIC_API_KEY`   | 108 | **108** |
   >
   > The empty shell export SHADOWS `.env`: django-environ reads `.env` only
   > for names absent from the environment, and an exported empty string is
   > present. So `env -u` is not a guard that keeps the key away from the
   > application — **it is the thing that makes the key available**, by
   > removing the shadow.
   >
   > **NONE OF THAT IS NEW, AND SAYING SO IS THE POINT.** Row **A11** in
   > `OWNER_INPUT_MANIFEST.md` already states the mechanism exactly —
   > *"`environ.Env.read_env` will not override a key already in the
   > environment, so the **108**-character credential in
   > `bbrose_design_os/.env` is never read"* — and already explains the
   > `409 vs 201` at its own lines 298-309. I re-derived from scratch, in this
   > session, a thing the manifest had written down, and was one edit from
   > filing it as a finding. **The defect is mine and it is the fourth
   > consecutive tranche of it:** I searched the launcher and the queue and did
   > not open the manifest, which is the artefact-scoped extent §AZ0(t) names.
   > The two-row table above is a re-measurement that CONFIRMS A11, not a
   > discovery.
   >
   > **The step still does not get struck and `env -u` still stays on every
   > `guarded_commit.sh` call** — but for the honest reason, which is that the
   > suite needs the key to resolve, not that it needs it suppressed. **A11 is
   > unchanged and still open:** the owner's shell exports an empty
   > `ANTHROPIC_API_KEY` that breaks the application on every invocation that
   > forgets the prefix.
4. **DONE** — and every commit since has gone through it with no override.

**Step 3 may not precede step 2 even if step 2 proves slow.** §AA: a guard
nobody has seen fire is not evidence of anything.

**If step 1 is large, the key stays shadowed and the size of the remedy is the
finding.** A green suite bought with unguarded spend is an invoice with a green
suite attached.

**You may NOT** modify any shell rc file, write a credential into any tracked
file, or print/log/echo/commit either key's value at any length in any form,
including partially masked. **Lengths only.**

**§AR4(5) is FALSIFIED** — the three failures were never inherited. `ad3db82`'s
bypass of the extent gate is now an **UNEXCUSED DEFECT**, is named as one in
§AY1(d), and the same reasoning may not be reused. Once step 4 passes, the
override has no remaining justification in this repository.

### AY-2 — the clear space. An ordering, phrased against the intruder.

```
1. MOVE THE INTRUDER   — whichever element is inside the clear space on the
                         run. If the vertical budget exists. Costs nothing.
2. SHRINK THE LOGO     — floor 12.0 mm print / 60 px screen. THE FLOOR DOES
                         NOT MOVE. See below: this step CANNOT close it alone.
3. REPORT              — "the front cannot carry the logo at ruled clear
                         space", and the logo comes off the front. Refer that
                         back; it is §AE2(c) and it is not yours to execute.
```

**BARRED: reducing clear space below 1.0× cap height.** Never move a bar
applies to bars set the same morning.

**BOTH STATES MUST CLEAR** — the front as emitted today, and the front as
emitted once C9 supplies the descriptor. Fixing today's intruder and closing
the row while the future one still collides is the reverse of §AW5(c)'s error
and is barred by AY2(b).

**The arithmetic that makes step 2 insufficient alone:**

```
requirement at 17.28 mm placement    3.0861 mm
requirement at the 12.0 mm floor     2.1431 mm
relief from the REQUIREMENT side     0.9430 mm
measured shortfall                   1.5124 mm
STILL UNCOVERED at the floor         0.5694 mm
```

Shrinking to the absolute minimum buys **62.3 %** of the shortfall. The rest
must come from geometry, and whether it does is a **measurement, not an
assumption**. Do not reach for step 2 first on the theory that shrinking is
sufficient. It is not, by arithmetic.

**§AU6(c) is LOST** — the floor fits with **+12.5138 mm** of horizontal headroom
on the real 28.80 mm front. The bet named the wrong axis. §AU0(c) predicted this
refusal in terms and called it the tranche's best output; it is upheld as
exactly that, and the bar does not move.

### AY-3 — what §AY does NOT unblock, named so you do not infer it

**§AU5's ordering is untouched.** AY1's guard is a **network** guard for a
different reservation. Building it does **not** discharge §AU5 and may not be
reported as discharging it. The §AE2(c) brand-string guard still gets built and
still gets watched refusing something before `hierarchy_lines` is supplied.

**C9 is still owed by the owner** and is still the single string between VQR-3's
five elements and a drawn front.

**No acceptance gate advances.** `owner_acceptance` is untouchable under
§AE0(a). Nothing here predicts a VALIDATE. **§AS2(2) still binds** — if this
tranche closes with no percentage moved, that is a reportable defect, reported
first, before anything above is described as progress.

### AY-4 — two new laws you will be held to

**§AY0(d) — an absence is a measurement and carries a search extent; a quantity
is a measurement and carries the state it was measured in.** Say where you
looked. Say which version of the document the number came off.

**§AY0(e) — a refusal to act is reported at the volume of an action.** §AE0(e)
says report failures loudly; this extends it to what you deliberately did
**not** do, and why. Going quiet at the edge of a reserved category is
indistinguishable from not noticing the edge. **§AX did this correctly and is
the model.**

---

## TRANCHE — §AU. THE VQR-3 FRONT. (NEXT, AFTER §BA.)

**The mandate below is unchanged and still governs. This block says what to do
first with it. §AY has been executed and this is now the first thing to do.**

**BEFORE YOU START, THREE THINGS §AY MEASURED THAT CHANGE THIS BLOCK:**

1. **AU-2's premise is dead.** It says *"the live front is 35.00 mm wide."* It
   is **28.80 mm** (`label_zone`), corrected at §AY0(b) and confirmed by
   measurement. §AU6(c) is already LOST and the floor already fits with
   **+12.5138 mm** of horizontal headroom. Do not re-run that measurement as if
   it were open; read AY-2 above.
2. **AU-2's second half is now C11, not a measurement.** "Build the C2 validator
   against the ruled set" is DONE — it exists, it is tight, and on the front
   production actually composes it reports **18 findings that no vertical move
   and no size reduction can clear.** §AU0(c) said a failure there would be the
   tranche's most valuable output. It was. It is not yours to close.
3. **`hierarchy_lines` is the state §AY2 cleared and production does not
   supply.** Neither production call site passes it. So AU-1's guard is not
   protecting a hypothetical: the moment you supply `hierarchy_lines` you make
   the front's copy real, and that is precisely the reservation §AU5 draws.

WI-3K did the most valuable thing available to it and got no percentage for it:
it **measured** which manifest row stops `pc.vqr3_artwork_composition` rather
than inheriting the answer. §AS2(5) had guessed **A1**. Measured, A1 blocks
`pc.vqr2b_reconstruction_measurement`, which is **VALIDATED 100/100**, and every
VQR-3 axis reads the emitted document rather than a photograph. The rows are
**C8, C2, A10**. All three are now ruled in §AU.

### AU-1 — the guard comes FIRST, and it is watched failing

> **THREE OF THESE FOUR STEPS ARE DONE. §AV DID THEM. READ THIS BOX FIRST.**
> The §AU text below is the owner's, reproduced as ruled, and it was accurate
> when written — §AV had not happened yet. It is stale now, and the stale
> version was still being read back as current one commit ago (AZ0(u)). Status
> against each step is inline below. **Step 3 is the only one open.**

**Do not supply `hierarchy_lines` yet.** `tools/reserved_copy.py` works and
`⟪PROVISIONAL⟫` now genuinely exists at `tools/reserved_copy.py:54` — §AK's
finding is discharged. **But its docstring scopes it to §AE2(b) headings and
explicitly excludes the product-name path as *"a different reservation with a
different remedy."* That remedy has never been built.** A placeholder descriptor
fed today is refused by nothing.

> **The last two sentences are FALSE at HEAD.** The remedy was built by §AV,
> which opens by recording that `reserved_copy.py` **cannot** be extended to
> cover this — the same negative result anyone re-reading the paragraph above
> will re-derive. A placeholder descriptor fed today is refused by
> `brand_string_report`, at three production call sites.

1. ~~Build the §AE2(c) brand-string remedy — extend `reserved_copy.py`'s scope
   or write a sibling.~~ **DONE — §AV, as a sibling pair.**
   `tools/brand_strings.py` (static, source) and
   `apps/ire/brand_string_runtime.py` (runtime, `brand_string_report` at 228).
   The two-instrument split is §AV's finding and is not optional: a static
   scanner cannot see a descriptor that arrives from a database row.
2. ~~**Watch it refuse a real violation.**~~ **DONE** —
   `apps/ire/tests/test_av3_brand_string_runtime.py`,
   `apps/ire/tests/test_aw_emitter_closure.py`.
3. **OPEN. THIS IS THE WORK.** Supply `hierarchy_lines` with `text` = the
   literal `⟪PROVISIONAL⟫` and `provisional: true`. **Measured: no production
   path supplies `hierarchy_lines` today** — the only match under `apps/`
   outside tests is a prose string in `container_line_weight.py:91`.
4. ~~Fail closed on every path to print, a proof, or an owner-facing
   artefact — and **see the closure fire** before trusting it.~~ **DONE** —
   §AW moved the closure to the emitter and
   `apps/pipeline/tests/test_av5_artefact_withheld.py` watches the artefact be
   WITHHELD. §AU5(4)'s separate obligation — anything reaching an owner
   OUTSIDE the document, e.g. a filename or a dashboard string — is named as
   out of scope in `brand_string_runtime.py`'s own docstring and is **not**
   discharged.

**If step 1 is large, the front stays unreached and the size of the remedy is
the finding.** A drawn front with an unguarded fake string on it is a worse
tranche than an undrawn one, and reporting that honestly is a pass of this item.

### AU-2 — measure C2's floor against the front before building anything on it

§AU3 ruled a **12.0 mm** minimum logo width and **1.0× cap-height** clear space.
The live front is **35.00 mm** wide. **Whether that fits, alongside the name,
the rule, the descriptor and the decoration, was not measured before the ruling
— and it is §AU6(c), the bet most likely to be lost.**

Measure it first. If it does not fit, the deliverable is *"AU3's floor is too
high for the front it has to live on"*, queued as a correction. **§AU8(f): the
floor is not reduced to make the fit pass.** A bar set five minutes ago is still
a bar.

Then build the C2 validator against the ruled set. **It is meant to be tight
enough that the existing emitted logo might fail it.** If it does, that failure
is the most valuable output of the tranche — §AU0(c), and it is why the
permissive option was rejected.

### AU-3 — the divider has THREE gates, not the two the manifest named

§AU2 rules the weight at **0.30 mm**, `authority: OWNER_RULED — §AU2`, in those
words. **`emitted` stays `False` until production actually draws it** and flips
in the commit that makes it true, not the one that makes it possible (§AU8(c)).
Recording a ruling as a measurement is §AK in the opposite direction.

Reading `apps/ire/compose_container.py` rather than the manifest: inside
`if direct_print and hierarchy:` the rule draws only `if language is not None`.
So the third gate is a **SUPPORTED motif language**, and the manifest was
incomplete on its own subject. **Which concepts satisfy that gate is a
measurement you take** — per AD0(a) it is not a condition to assume is met.

### AU-4 — the shape is ruled, the string is not

```
hierarchy_lines = [
    {"text": "⟪PROVISIONAL⟫", "rel": <yours>, "kind": "descriptor"},
]
```

`len(hierarchy_lines) == 1` is a **CONTRACT number** in the §AD1(d) sense — a
second tier supersedes §AU1 rather than extending it. `rel` is yours: it is
dimensionless and typographic, and **§Z1(b) binds absolutely — it may scale a
chosen size and may never be derived from a zone height or any other millimetre
quantity.**

### AU-5 — what you may NOT claim at the close

**Do not claim `pc.vqr3_artwork_composition` VALIDATES.** One of its five
elements carries a placeholder until C9 lands and V3 §10 allows no partial
credit. What §AU predicts is that **all five elements are reached for the first
time** — and per AD0(a) even that is a prediction until you measure it, so
report the measured version rather than restating the table in §AU4 of the
clearance file.

**§AS2(2) still binds.** If this tranche closes with no percentage moved, that
is a reportable defect and it is reported first, not argued around. §AU makes
movement possible; it does not license claiming it.

### AU-6 — the standing invitation §AU0(a) opens

C8 was **two rows wearing one number**: a structure that was rulable in a
sentence, bundled with content that was not. Split, it stopped blocking
everything and started blocking one string.

**At least three more rows in `OWNER_INPUT_MANIFEST.md` have this shape.**
Finding them and proposing the split — structure the owner can rule in a
sentence, content he still owes — is high-leverage work you may do under §AE1
without asking. Propose the split; do not rule the structure yourself.

**The counter-bet is §AU6(d):** if two ruled structures get superseded by their
own content inside one tranche, splitting was premature and the rows should have
stayed bundled. Watch for it.

---

## THE MANDATE IN SIX LINES

Build the **23 critical-path nodes** to 100%. Decide everything yourself except
four categories. Where a reserved input is missing, substitute a loudly-marked
provisional, keep building, and log the ask. Improve performance freely with a
number on each side. Write every decision down as a section **before** the code
that depends on it. Stop only on the AE7 conditions.

**You may move four of the five dimensions. `owner_acceptance` is untouchable.**

---

## WHAT YOU MAY NOW DECIDE ALONE (§AE1)

Everything not in the reserved list. Architecture, algorithms, data structures,
error handling, test strategy, fixtures, dependencies within the stack. All
numeric thresholds and calibrations (§U: name the statistic; §V: the ruling is
the number, not the arithmetic). All layout that follows from a measurement.
Roadmap sequencing. Test-suite composition including deletion, if ruled with the
lost coverage named. Performance and refactoring. Your own working practices.

**Three explicit unblocks, stated because you would otherwise stay paralysed on
rules that §AE has now changed:**

- **The zone contract is yours.** You may add a zone and re-derive
  `zone_set_hash` and `combined_confirmation_hash` — provided you first commit
  an EXECUTOR-RULED section giving the zone's geometry, permitted techniques,
  why it is distinct rather than an instance of an existing zone, and the full
  hash consequences. **`z_wrap` can be resolved this way and the jar unblocked.**
  AD3(c) is superseded. §X2(a) still makes it a CONTRACT change — §AE changed
  who may make one, not how carefully.
- **Flake re-run grants are yours.** A189's bound holds: one cause node per
  grant, `invocations_allowed` incremented in a committed diff with the cause
  named. Registering without a cause is still illegal.
- **The §Y2 classifier may be widened** — but only with the full repo-wide
  re-classification and a re-derived `REGISTERED_UNDECLARED` in **one** commit,
  exactly as AD6(c) specified. And **`UnitAnalyser.run()` may be fixed** — write
  WI-3E's honest red first, so the fix has something to turn green.

**AD1's four surfaces at 6.0 pt stands and is DERIVED, not reserved.** Build on
it. When the real WARNINGS/MANUFACTURER copy arrives, the number is
**re-derived automatically, not re-ruled.** If your own measurement against the
provisional shows more than four are needed, **report the provisional's
inadequacy as the headline** — do not silently adopt five.

---

## THE FOUR THINGS YOU MAY NEVER TOUCH (§AE2)

Not because they are important — everything is important. Because **you cannot
produce them without producing something false.**

**(a) Physical-world inputs.** Bottle photographs, calipers, die/stock spec,
`SUPPLIER_DATA`, EAN, distributor, any dimension of a physical part not already
in the repo. There is no such thing as a derived measurement.

**(b) Regulated, legal and liability-bearing copy.** The 7 WARNINGS lines, the
3 MANUFACTURER lines, the continuation-marker wording, ingredient text, claims,
origin, certification marks. **Do not draft it. Do not suggest wording. Do not
adapt it from a comparable product. Do not fill it in "just to see the
layout".** A generated cosmetic warning that reads correctly, on a product
actually manufactured and sold, is a real harm to a real person — and it passes
review precisely because it looks like copy.

**(c) Brand identity and taste.** Brand usage rules, the confirmed face,
`BRAND_LOGO_PATH`, typeface licensing, shade authority, motif selection, the cut
list — and **the two-way optimal-allocation tie at 6.0 pt.** That tie stays
reserved on purpose: both are optimal by every measurement available, so no
instrument can separate them, so any choice you make is taste wearing a
heuristic's clothes. **Render both. Queue both.**

**(d) Terminal and acceptance gates.** `pc.acceptance_outcome`, every
`*_OWNER_VISUAL_REVIEW`, RBV-3's format review, GATE_2. **No status containing
`OWNER_ACCEPTED`, `ACCEPTED`, `APPROVED` or `SIGNED_OFF` is written by you,
anywhere, for any node, ever.**

**Standing prohibitions, not delegable:** supplier outreach is **permanently
WITHDRAWN (§C2)** — no enquiry, no drawing request, no vendor account. **AI
never generates geometry.** No irreversible action outside the repository. No
history rewriting: no force-push, no rebase over committed sections, no amend of
a commit another section cites by hash.

---

## THE PROVISIONAL PROTOCOL (§AE3)

**Every** provisional carries the literal token `⟪PROVISIONAL⟫` in its text and
`provisional: true` in its record. One grep finds all of them.

**Before the first provisional is used, write the fail-closed guard**: no
artefact in `OUT`, no committed render, no file destined for print or owner
review contains `⟪PROVISIONAL⟫` while also marked final. Provisional artefacts
are legal and are marked provisional. **See the guard fail once before relying
on it** — §AA: a guard nobody has seen fire is not evidence of anything.

Provisional copy renders as the token, the field name, and the line budget it
stands in for. **Never as prose.** The EAN placeholder is never a syntactically
valid EAN — a well-formed barcode that scans to the wrong product is exactly the
error the marking rule exists to prevent.

A ruling that depends on a provisional says so in its first line, and its named
bet is automatically *"wrong if the real value differs materially."* Those
rulings are **re-derived when the real value lands, never grandfathered.**

Log every ask in `OWNER_INPUT_MANIFEST.md` **continuously**, not at the end.

---

## HOW YOU RULE (§AE0(b))

When you decide something that would previously have come to the owner:

1. Write it as a section in `OWNER_BLOCKER_CLEARANCE.md`, headed
   `## §AF — EXECUTOR-RULED — <subject>`. Letters continue §AF, §AG, §AH…
2. Close it with
   `RULED BY: executor under §AE1. REVIEWABLE. NOT OWNER-ACCEPTED.`
3. **Carry a named bet** — the sentence *"this ruling is wrong if…"*, stating
   the observation that would overturn it. A ruling with no losing condition is
   a preference with a section number on it.
4. **Commit the section BEFORE the code that depends on it.**
5. The file stays **additive-only**. Deletions **0**, forever. A correction is a
   new section naming the defect by line number (AC0(c)). If §AH overturns §AF,
   §AH names §AF by section and line and says what changed.

---

## TRANCHE 1 — SPRINT 15 (§AD, never dispatched)

### WI-0 — charter lands, evidence gets rescued

**(a)** Commit §AD, §AE, the two ANSWERED blocks and `OWNER_INPUT_MANIFEST.md`
**before any code.** Prove additive-only from `git show --numstat`:
`OWNER_BLOCKER_CLEARANCE.md` shows `<n>  0`. Record `<n>`.

**(b)** Run **both** grep forms against `'^## §AD'` and `'## §AD'` and record
both. §AD7(b) states them as of signing and tells you to re-measure anyway,
because committing changes the file.

**(c) RESCUE `/tmp/wiv_suite2.txt` NOW, before anything else.** Copy to
`bbrose_design_os/docs/roadmap/palt_m6/wiv_suite2_20260819.txt` and commit. It
is the only surviving record of the only run in which the flakes fired, and
`/tmp` does not survive a reboot. **If it is already gone, say so plainly and
stop WI-3B** — do not reconstruct it, do not approximate it, do not substitute
HEAD's run.

**(d) Read it WHOLE.** `sed -n` ranges or `cat`. **No filters.** You destroyed
your own data with `grep -v` twice last sprint, both times on the WARNINGS
section, and you wrote that down yourself.

**(e)** Kill the two orphaned background waiters ("Wait for the ire+pipeline
suite to finish", "Block until suite finishes then show result"). They have been
polling ~19 hours for a signal from a run that finished in 593 seconds. **Never
block on a suite in a background task with no timeout** — foreground it to a
named output file, or give the waiter a deadline and treat expiry as a FAIL. A
waiter that cannot fail cannot report.

### WI-3A — `product_id` (AD4)

Declare extent before looking (rule 3l).

`test_browser_profile_editor.py:115` mints
`product_id=f"CO-B{DesignTask.objects.count()}"` into a `unique=True` column
(`core/models.py:89`), counting the **wrong model**, at a value that is 0 in a
fresh test DB — so all seven call sites (525, 543, 562, 579, 624, 670, 686)
produce `CO-B0`.

Fix it — **not** by counting `Product` instead; a count over any table is the
same class of defect. Then **re-run the two flakes against the fixed fixture and
record whether the failure mode still reproduces.** Still failing is also a
finding: it rules out the cheapest hypothesis, which is what a cause node is
for. Census the same pattern repo-wide; report `X.objects.count()` feeding any
other unique column as a finding.

Under §AE1 you may now grant the re-run yourself if the cause is established —
one cause node, committed diff, cause named.

### WI-3B — triage all twelve failures (AD2)

Twelve rows: test id, file, assertion text, classification from the closed set
`MATCHES_HEAD` / `FIXED_SINCE` / `FLAKE_CANDIDATE` / `UNCLASSIFIED`.
`UNCLASSIFIED` is legal and preferred to a guess.

All twelve, **not** the seven: *"5 of them are the same 5 that fail at HEAD"* is
an assumption about failure identity, and that is exactly the inference the
substitution check exists to test. Match against HEAD's 5 explicitly and
**record the match as a finding, not a premise.**

**No cause column. No cause sentences.** *"A confident wrong cause is worse than
none, because it stops anyone looking again."*

### WI-3C — `z_wrap`: see it fail, then rule it, then fix it

**Order matters and it is not negotiable.** Confirm the guard fails on the jar
archetype at HEAD and quote the failure verbatim. **Then** write the
EXECUTOR-RULED section. **Then** fix it.

Ruling it without ever watching the guard fire wastes the one cheap opportunity
to verify the instrument on a real violation — and this violation is real:
`container_contract.py:573` emits `z_wrap` from the jar branch, outside the
confirmed set, in production, and has been doing so all along.

### WI-3D — the four-surface back panel at 6.0 pt (AD1)

Four surfaces, 6.0 pt, splitting on, one split. **Render BOTH optimal
allocations into `OWNER_REVIEW_QUEUE.md`** — no tie-break in the packer, not the
first, not by any property of the allocation (§AE2(c)).

Continuation marker: **charged a line**, carrying `⟪PROVISIONAL⟫`. No invented
wording anywhere.

**Scratch does not go in `OUT`.** The WI-Y near-miss stands: the tool wrote
measurement scratch into the review directory and those PDFs are **not
byte-stable** — the same panel hashed `cf006867` then `98bbe5ab` across runs.

### WI-3E — `UnitAnalyser.run()` — red first, then fix

`run()` appends to `self.findings` and increments `self.checks` without
resetting, so a second call on one instance doubles both. `TREE_CHECKS = 839`
is correct only because every caller constructs a fresh per-file analyser.

Write the test — call `run()` twice, assert the second returns what the first
did — **watch it fail**, then fix it under §AE1. WI-Q's lesson was a denominator
that quietly stopped moving; this is the mirror.

### WI-3F — the §Y2 number gets its qualification

`12` is **the count of guards written in a syntax the census recognises**; 14
are declared by name. Add that qualification wherever the number is cited. Then
you may widen the classifier if you rule it — repo-wide re-classification and a
re-derived register in ONE commit, or not at all.

---

## TRANCHE 2 ONWARD — THE 23 CRITICAL-PATH NODES

From `progress_tracker.json`, in order. Active node is
`pc.vqr3_artwork_composition`; declared next is
`brand_gov.minimum_component_library`.

```
palettes.palt_m1_foundation          quality.rbv4_claude_review
quality.generalized_material_engine  quality.rbv5_comparison_gate
palettes.palt_m2_geometry_layout     pc.vqr2b_reconstruction_measurement
palettes.palt_m3_mechanism           ire.design_graph_v2
palettes.palt_m4_powder_materials    brand_gov.minimum_component_library
palettes.palt_m5_pilot_p1            pc.vqr3_artwork_composition   ← active
palettes.palt_m6_powder_material_engine  pc.vqr4_typography_quality
palettes.palt_m7_pilots_p2_p3        pc.design_adjustment_studio
pc.vqr1_m3_integration               pc.vqr5_materials
quality.rbv1_reference_standard      pc.client_presentation_artboard
quality.rbv2_visualization_renderer  pc.acceptance_outcome  ← owner's, terminal
quality.rbv3_review_package
```

**Sequencing is yours (§AE1).** The order above is the recorded critical path,
not an instruction — reorder it if you can justify the reorder in a section.

**Definition of done per node (§AE4):**

- `CEILING_REACHED` — the only thing left is an `OWNER_INPUT_MANIFEST.md` row.
  **Name the row.**
- `COMPLETE_BY_EXECUTOR` — all four movable dimensions advanced as far as they
  go, `owner_acceptance` the sole outstanding dimension.
- **`COMPLETE` alone remains an illegal status.** It never appears without one
  of the two qualified forms. "Complete" is the word that hid every unfinished
  thing this programme has ever found.

**Out of scope:** M4b sub-branches, the palette P2/P3 pilots beyond the
critical-path node, the quality backlog. If a critical-path node genuinely
depends on one, that dependency is a **finding** — name it, pull it in
explicitly, report it.

---

## PERFORMANCE (§AE5)

**Improve freely. A number on each side or it is reverted on sight.**

A change described as faster with no measurement is the 0.3 µs lesson in general
form: you built a complete causal story about media accumulation — 101,686
files, 23,745 orphans, 7.9 GB — and had it ready to write up before measuring.
The measurement was **0.3 microseconds.** The story was excellent and the effect
did not exist.

A behaviour-changing refactor needs a test that passes **before** the refactor
and after. Declare before realize.

The suite is ~7,250 tests at ~10 minutes and you will run it many times
unattended, so cutting it is genuinely valuable — parallelisation, fixture
scope, database setup all fair game. **But** the canonical serial run
(`venv/bin/python -m pytest -q -p no:randomly`, from `bbrose_design_os/`, run
alone, output captured whole and never tailed) is still run at every close and
is still the number reported. A faster suite that reports a different failure
count is not a faster suite.

**Never optimise an instrument while it is being used to judge something.**
Never move a bar; do not move the ruler either.

---

## STOP CONDITIONS (§AE7) — halt, write what you have, wait

**(a)** You would have to fabricate a physical measurement or draft reserved
copy, and the provisional protocol does not cover the case.

**(b)** Two owner rulings genuinely contradict and no reading reconciles them.
Write both readings and the consequence of each. **Do not pick.**

**(c) SPEND.** Lifetime provider cost across the whole programme is **$27.05**
over 226 rows. This run may add up to **$50.00**, then halts and reports. The
cap is nearly twice the programme's entire history and it exists because an
unattended loop with an API key and no ceiling is the one failure mode that
costs real money while looking like progress. **The owner can raise it. You
cannot.**

**(d)** Any irreversible action outside the repository.

**(e)** The suite's failure count rises and you cannot attribute the rise within
one sprint. **Do not proceed past an unexplained regression** on the theory that
it will become clear later.

**(f)** You find yourself about to write `OWNER_ACCEPTED`, contact a supplier,
or have a model produce geometry. These should be unreachable. If one is
reached, **the reasoning that got there is worth more than the sprint** — report
it as the headline.

---

## HOW YOU STAY HONEST WITH NOBODY WATCHING (§AE0(e), §AE6)

**Every close report opens with DEFECTS AND REVERSALS** — what broke, what you
ruled and then unruled, what you measured wrong, what you believed and then
disproved. Progress comes after.

**Spawn a fresh subagent at every close** with no memory of the sprint. Give it
the close report and repository access and one instruction: *find the claims in
this report the repository does not support.* Its findings go in **verbatim**,
including the wrong ones. A suite cannot verify itself and neither can a run. A
false positive from an independent check is cheaper than a true negative from a
self-check.

**Every count is taken from the tool at the moment of writing** (AC0(b)), and
**no count is predicted from the shape of a previous result** (AD0(a)) — that
law exists because the owner broke it and you caught it.

---

## THE INVARIANTS (§AE9) — asserted at every close

**(a)** No `OWNER_ACCEPTED` / `ACCEPTED` / `APPROVED` written by you, anywhere.
**(b)** Every executor ruling is a committed EXECUTOR-RULED section, committed
before its code, carrying a named bet.
**(c)** `grep -rn '⟪PROVISIONAL⟫'` finds every provisional; the fail-closed
guard is committed and has been seen to fire.
**(d)** `OWNER_INPUT_MANIFEST.md` is current.
**(e)** No supplier contacted. No irreversible external action. No history
rewritten. No geometry generated by a model.
**(f)** Provider spend added is reported; the run halts at +$50.00.
**(g)** Every optimisation carries a before and an after; the canonical serial
suite run is the reported one.
**(h)** DEFECTS AND REVERSALS leads; the subagent audit is verbatim.
**(i)** `OWNER_BLOCKER_CLEARANCE.md` deletions **0**. Every commit. Forever.
**(j)** The final deliverable is the node table.

---

## THE FINAL DELIVERABLE

**All 23 critical-path nodes. Five dimensions each. One line of evidence per
advanced dimension. The `OWNER_INPUT_MANIFEST.md` row blocking every node short
of its ceiling.**

A repository where **nothing is unstarted and every remaining gap has the
owner's name on it.** That is what 100% means here.

Plus: the full commit list by hash; both §AD grep counts; the twelve-row triage
table; the `z_wrap` failure verbatim and its ruling; both 6.0 pt allocations
rendered and queued; the `product_id` re-run result stated either way; the
canonical suite result in full; provider spend added; before/after numbers for
every optimisation; and **every defect you found in yourself.**

---

# ⚠ MID-RUN OWNER AMENDMENT — 2026-08-20 17:2x — READ BEFORE ANYTHING ELSE

**This block was added while your TIER_2 was mid-suite.** It was written into
*this* file and NOT into `OWNER_BLOCKER_CLEARANCE.md`, deliberately: six files
under `apps/` and `tools/` read the clearance file
(`test_rbv3_review_package.py`, `test_rbv3_views.py`,
`test_silhouette_tolerance_separation.py`, `test_h2_views.py`,
`test_h2_design_request.py`, `rbv4_review.py` and the services behind them), so
appending to it during a run is the contamination defect already on your own
list. Nothing in `apps/` or `tools/` reads this launcher. That is why it is here.

## WI-0′ — YOUR FIRST ACTION ONCE TIER_2 CONCLUDES

Before any further work, transcribe the block below **verbatim** into
`OWNER_BLOCKER_CLEARANCE.md` as a new section and commit it alone, ahead of any
code. You are the transcriber, not the author: it is signed `SIGNED: BBrose`,
it is an OWNER ruling under §AE2(d), and you may not edit a word of it. If you
believe any clause is wrong, implement it anyway and raise the objection in your
close report.

---

## §AS — OWNER-RULED — a tranche that closes with no node moved has not built the roadmap, whatever else it produced

### AS0 — WHAT WAS MEASURED

Between `a45b615` (09:42) and `614a6dc` (17:09) on 2026-08-20 the run produced
**27 commits** and **thirteen executor-ruled sections, §AF through §AR**.
Measured against `docs/roadmap/progress_tracker.json` in the same window:

- the tracker was **not written once**. Its last commit is `04977dc`,
  2026-08-18, two days before the charter.
- `pc.vqr3_artwork_composition` — the active node at the moment the charter was
  issued — is `NOT_STARTED`, `implementation_percent` 0, `validation_percent` 0,
  `visual_quality_percent` 0. Unchanged.
- `pc.vqr4_typography_quality` — likewise `NOT_STARTED`, 0/0/0.
- eleven nodes carry `owner_acceptance_percent: 100`. **All eleven predate the
  charter.** §AE0(a) has held perfectly and this section does not doubt it.
- no cost-bearing ledger has been written since 2026-08-17;
  `render_spend/queue_ledger.json` is dated 2026-08-10. Roughly **$0.00 of the
  $50.00 cap** is spent, because nothing that emits artwork has run.

By file, the run went: `OWNER_BLOCKER_CLEARANCE.md` 14 times,
`OWNER_REVIEW_QUEUE.md` 13, then test files and `guarded_commit.sh`.

### AS1 — THE RULING IS NOT THAT THE WORK WAS WASTED

It was not. §AR establishes that the sanctioned commit path had been refusing at
declared extent for **eight days** with 44 `MANIFEST_FILE_UNDECLARED`, so build
work could not be committed through it at all. Repairing the road before driving
on it is correct, and §AK — the `⟪PROVISIONAL⟫` marker never once used, a
fabricated quantity live on the production path — is worth more than a node.

**The defect is not the day's content. It is that no instrument exists that
would have noticed.** §AE4 defines done as 23 nodes at their ceiling and then
never asks, at any checkpoint, whether a node moved. A charter that measures its
own output only in sections it wrote will keep producing sections. Seven more
hours of the same shape ends with forty clearance sections, the same statuses
and the cap unspent, and every individual commit defensible.

**A programme can be rigorous in every step and still not be going anywhere.
Rigour is not a direction.**

### AS2 — THE CHECKPOINT (this is the operative clause)

1. **Every close report opens with a NODE DELTA table**, immediately after
   DEFECTS AND REVERSALS: node id, and the before/after of all five dimensions,
   read out of `progress_tracker.json` at both ends. Nodes that did not move are
   listed with their unchanged numbers. **An empty table is written out in
   full, not omitted.**
2. **A tranche closing with zero node movement is itself a reportable DEFECT**,
   named as such in DEFECTS AND REVERSALS, carrying the reason. It is not
   automatically wrong — §AR is a legitimate reason — but it must be *claimed*,
   not left to be noticed.
3. **You may not open a new `## §Ax — EXECUTOR-RULED` section while the
   preceding tranche moved zero nodes**, until either a node has moved or the
   blocking reason is written into `OWNER_INPUT_MANIFEST.md` as a row with my
   name on it. Governance is not rationed; governance *ahead of* build is.
4. **The exception, and it is deliberately narrow:** a section required to
   unblock a node you are actively building is not "ahead of" anything. Say
   which node, in the section.
5. **`pc.vqr3_artwork_composition` is the next thing built.** The commit path is
   clear as of `extent_asserted: YES`; the reason for the eight-day detour is
   discharged. If it cannot advance, the manifest row that stops it is the
   deliverable, and A1 — the five calibrated ruler-in-plane photographs — is
   almost certainly that row.

### AS3 — WHAT THIS DOES NOT CHANGE

§AE1 stands entirely: you still decide every engineering, geometry, threshold,
layout, contract and architecture question alone. §AE2's four reserved
categories stand. `owner_acceptance` remains untouchable and has been
untouched. The $50.00 cap stands and is essentially unspent — **spending it on
a node is the intended use, and $0.00 spent is not a virtue here.** Nothing in
§AF–§AR is reopened, withdrawn or doubted.

### AS4 — THE BET, NAMED SO IT CAN BE LOST

**This ruling is wrong if** the next tranche moves a node and the movement is
hollow — a percentage raised because a checkpoint asked for one. I would rather
have an honest empty NODE DELTA table than a dishonest full one, and clause
AS2(1) requires the empty table precisely so that producing one is a legal
outcome. The counter-evidence to watch for is a dimension advancing in the same
commit that introduces the checkpoint, or a `visual_quality_percent` moving
without an instrument reading behind it — which §AE0(a) already forbids and
which this section makes tempting for the first time.

`SIGNED: BBrose (PROJECT_OWNER, via Cowork session)  DATE: 2026-08-20`

---

**Operational.** Git root `bbrose-systemOS`, pytest root `bbrose_design_os`.
**The working directory silently reverts when a compound command fails** — use
absolute paths or re-`cd` every invocation. Never read an artefact through a
filter.

**"COMPLETE" is not a legal status. A suite cannot verify itself. No
self-approval at the terminal gate. AI never generates geometry. Never move a
bar — fix the instrument.**
