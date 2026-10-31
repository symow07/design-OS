# WORK ITEM LEDGER

§W (2026-08-18) made this file binding: *a work-item label that names nothing
real is a stale claim.* Carry the names here and check them against `git log`
before citing one.

A row may only be marked LANDED with a commit hash that `git log` shows.

**Labels repeat across sprints. A bare "WI-F" is ambiguous and always has
been** — sprint 7 and sprint 9 both have one, and they are unrelated work.
Cite the sprint with the letter, or cite the hash.

## SPRINT 11 — §Z

**§Z opened by reversing a sprint-10 conclusion.** WI-I (sprint 10) determined
that `front-brand`'s 2.115 was "6.00 pt printed" and that §W2 was raising a
false FAIL. That was backwards. `pdf_ai.py:184` is
`c.setFont(face, node.size_pt)` with **no `* mm`**, while `:360` is
`c.setLineWidth(stroke.width_mm * mm)`. The artefact really carried 2.58 pt
type: the axis was right and `_front_typography` was the defect.

The law §Z1 drew from it governs every row below — *`_mm` is millimetres and
the emitter converts; `_pt` is points and it does not; the emitter is correct
and is not to be changed.* And the working rule: **a claim that contradicts an
artefact is a finding about your instrument. Read the producer before ruling
on what a number means.**

| WI | Ruling | What it is | Commit |
|---|---|---|---|
| WI-0 | §Z/§Y4 | §Z enters the repo at sprint START — 170 insertions, 0 deletions; queue, launcher, 22 gate-ledger lines | `8d90f29` |
| WI-J | §Z1/§Z2 | `front-brand` set at an explicit 6.0 pt; every `zh`-derived `size_pt` removed; required negative control; 30-run census re-run | `dd0d60b` |
| WI-K | §Z3 | Back-panel copy set at `BODY_BACK`'s own capability-table floor, not the disclosed fallback; §X2 re-measured in mm and characters | `24fbd41` |
| WI-L | §Z4 | The hairline zero-height defect — `_path_bbox` consults stroke width; a fix, not a wider tolerance | `50fe992` **+ `bfa4b7e`** |
| — | §Z4 | Sprint-11 close: ledger hashes, red-count sentence, launcher rewrite | `2181499` |

**⚠ WI-J, WI-K and WI-L are all reused labels, and this is the worst
collision in the file.** Sprint 7 declared *there is no WI-J* — a label carried
in someone's head for work that does not exist. Sprint 7's WI-K is `1c47255`
(the typography axis passing on three unmeasured flags) and its WI-L is
`479ebd6` (that sprint's own launcher rewrite). **None of the three shares
anything with the rows above but the letter.** Cite the sprint or cite the
hash; a bare "WI-L" now names two different commits four sprints apart.

**Read the WI-K row as written.** The back panel's resolved size on today's
production path is 5.0 pt before and 5.0 pt after — `propose_zones` gives this
bottle SCREEN_PRINT on `BODY_BACK`, whose table floor is the fallback's own
number. What changed is that composer and axis now read ONE record instead of
two sources, which is the defect; the artefact is unmoved and the queue says
so. A reader taking that row as "the type got bigger in production" would have
it wrong.

**Read the WI-L row as written too.** `elements_outside_artboard` — the number
§Z4 warned "could change an answer" — is **4 before and 4 after**. The fix is
not inert (a stroked outline went from 1.805 mm past the trim to 1.915 mm), it
is that nothing on this sheet sits within a stroke's half-width of the edge.

**WI-L is the only row in this file with two hashes, and the second one is a
correction.** `50fe992` is the work. `bfa4b7e` is there because the full suite
came back **8 failed against §Z4(c)'s stated 5**, and all three extra failures
were one cause: the WI-L test file entered the repo carrying two pure
source-string guards with neither the declaring name nor the declaring
docstring §Y2(b) requires. §Y2(d) — *this rule is general, it is not scoped to
the two tests that prompted it* — caught its own author one sprint after he
wrote it. Both guards are kept (§Y2(a)) and both now declare what they are.
**Registering them was the wrong repair twice over:** the register only
shrinks, and `apps/ire` is the converted area, so an entry there would have
contradicted the area's own status. A reader who takes the second hash as a
second piece of work would have it wrong; it is the first one's compliance.

**Red count, stated explicitly as §Z4(c) requires: 5 failed / 3 skipped before,
5 failed / 3 skipped after, and they are the same five tests by name.** Gate
keys 16 / 69 / 4 before and after, from `tools/gate_registration.py` — the
committed census, not a script written to answer this question.
`pc.vqr3_artwork_composition` is `NOT_STARTED` at 0 / 0 / 0, untouched. The
§Y2 register is **58 before, 58 after**; the census total moved 64 → 66 and
the declared count 6 → 8, which is WI-L's two guards and nothing else.

**Nothing from §X2 is built, four sprints running.** WI-K re-measured the panel
against it, as §Z3(c) required, and the overflow got worse: at 6.0 pt the panel
holds 175 of 431 committed characters. No copy was written and none may be.

## SPRINT 10 — §Y

**§Y4 made this file, `OWNER_REVIEW_QUEUE.md` and `NEXT_SESSION_LAUNCHER.md`
commit-at-sprint-START, standing.** Sprint 9 overwrote an uncommitted launcher;
the structural answer is that the handoff documents are never the thing sitting
between an uncommitted edit and a rewrite. This section was opened before any
sprint-10 code was written.

| WI | Ruling | What it is | Commit |
|---|---|---|---|
| WI-0 | §Y4 | §Y enters the repo — 201 insertions, 0 deletions, no renumbering | `cdefc99` |
| WI-0 | §Y4/§Y5 | Governing files committed at sprint START; appendix label upgraded to byte-verified | `82a8131` |
| WI-G | §Y1/§Y2 | Zone may tighten a floor, never loosen it; source-string guards declare what they are | `75452a9` |
| WI-H | §Y3 | The false docstring, then the branch triage from call sites — REACHABLE, kept | `1d7a962` |
| WI-I | §Y4 | **NOT BUILT — scope question, stopped and queued.** The determination only | `7aebe63` |
| — | §Y4 | Sprint-10 close: ledger hashes, launcher rewrite, §Y2 backlog + `.code` finding queued | `234aa3d` |

**No row above claims LANDED without a hash.** Two gaps were opened deliberately
and both are now closed: the second WI-0 row with `82a8131`, and the close row
with `234aa3d`. Each was written as a *named* gap rather than a blank, because a
blank cell in a ledger read six months later is indistinguishable from a cell
nobody filled in — and this file exists to stop exactly that reading. The commit
that closes a gap is always the one *after* the work, so the last row of a sprint
is filled in by a one-line follow-up; that follow-up does not get a row of its
own, or the file never terminates.

**Read the WI-I row as written.** It has a hash because the *determination* was
committed, which is what §Y4 asked for — not because the front type was wired to
a surface. Nothing was: the premise turned out to be false (§W2's floor already
reaches those runs) and the number it judges is a drawing size in millimetres,
not a print size. The finding is in `OWNER_REVIEW_QUEUE.md` under
*2026-08-19 (sprint 10, WI-I)* and it needs a ruling. A future reader counting
five hashes in this section and concluding five things were built would be
making exactly the mistake this file was created to stop.

## SPRINT 9 — §X

| WI | Ruling | What it is | Commit |
|---|---|---|---|
| WI-0 | §X1 | `OWNER_BLOCKER_CLEARANCE.md` enters the repo — §W + §X, verbatim, additive-only | `dcc518c` |
| WI-F | §X3 | Direct tests for `reconstruct_container` — 23 tests, killed the M3 mutation nothing else caught | `f6aaffb` |

**⚠ WI-F is a reused label.** Sprint 7's WI-F is `ed0ee98` — font metrics
being discarded half per call, in the VQR-3 arc. Sprint 9's WI-F is `f6aaffb`
— `reconstruct_container` coverage, in the §X arc. **They share nothing but
the letter.** This is the first collision in the ledger and the reason the
rule above is now written down: the file was created because sprint 7 cited
labels that named nothing, and a label that names *two* things fails the same
way, one sprint later.

Nothing from §X2 was built (X3(c) forbids it). No row here claims otherwise.

## SPRINT 8 — the §W rulings

| WI | Ruling | What it is | Commit |
|---|---|---|---|
| WI-A | §W5 | Container placeholder allow-list — EAN (§B1) + distributor (§B2) only | `4004735` |
| WI-B | §W3 | Overlap: type-over-type blocks, type-over-artwork does not | `95d3de2` |
| WI-C | §W2 | Print-method capability table governs min text size on ALL runs | `57d4823` |
| WI-D | §W4 | Recorded weight rationale for the container front rule | `e8c4406` |
| WI-E | §W1 | Full-scale back panel at true dimensions, untruncated copy | `7de2369` |

## SPRINT 7 — as verified against `git log`, not as remembered

There is **no WI-H and no WI-J**. They were labels I carried in my head for
work that does not exist under those names; `369d3a4` is the owner queue.

| WI | Commit | What it was |
|---|---|---|
| WI-D | `8c83954` | The false claim had a mechanical cause — a truncated test message |
| WI-E | `04977dc` | V3 §10 refused the VQR-3 advance; the revert is the point |
| WI-F | `ed0ee98` | Font metrics existed and were being thrown away, half per call |
| WI-G | `31227fc` | Composition producer supplies two facts and REFUSES the third |
| WI-I | `b003f17` | The §V4 premise guard lived only in a test |
| — | `369d3a4` | Owner queue (not a WI) |
| WI-K | `1c47255` | Typography axis PASSED on three flags nobody measured |
| WI-M | `4f86914` | Composition axis said "not measured" about a defect it had found |
| WI-L | `479ebd6` | Sprint-7 launcher rewrite + owner queue addendum |
