# M6 — MEASUREMENT ADEQUACY AND N CLOSURE

Follows `M6-DRIVER-COMPLETENESS` (`7215388` → `af7ce42`), law at `eb20aad9698e1825`.
Owner authorization: transmission of this brief authorizes Section A and the third
amendment. Stop and object if any of it is wrong.

---

## SECTION A — OWNER RULINGS

### A5. Your least-confident question — ruled, and neither option was right

You asked whether extending the A3 precision principle to the 1a validity verdict was the
principle's intended reach, or whether the hashed "≤ 0.80 → VALID" already ruled and the
three FAILs should have been committed with the precision question raised afterward.

Ruling: **the stay was substantively correct and procedurally under-declared.**

The distinction that makes it correct: my earlier side-declaration attached a *consequence*
the law did not contain. Yours attached none. The law says "if the matrix contains a pair
at or below 0.80" — that presupposes the matrix contains measurements. A reading 0.0022
from the ceiling whose replicate spread is 0.167, and whose two replicate seeds land on the
other side, is not a measurement of which side of the ceiling it falls on. It is the same
defect class as the constant-vector Spearman and the silent zero: a computation returning
a plausible value from an input that cannot support the inference drawn from it. You did
not amend the law. You found its precondition unmet.

Committing the FAILs and challenging afterward would have been worse, and for a reason
worth recording: a committed verdict acquires inertia. Every subsequent node reasons from
it, and the challenge then has to overcome not just the number but everything built on it.
"Commit now, challenge later" is how an unreproducible number becomes load-bearing.

The procedural correction: it may not remain a per-case judgment applied by whoever notices.
It is hashed in Phase 1 as a general precondition on every threshold comparison in the
protocol, and applied retroactively. That retroactive sweep can unmake a PASS as easily as
a FAIL, and that symmetry is the whole point.

### A6. The N deadlock is dissolved, not decided

You correctly identified a drafting defect in your frozen readings — `valid_by_margin`
anchors on a minimum replication that cannot move; `degenerate_by_margin` never names which
rho — and correctly refused to re-draft a frozen declaration. You then asked me to choose
between the commissioned-anchor and the ensemble-consensus interpretation.

I choose neither, and no re-drafting occurs. Both branches share a precondition — that
0.7978 at seed 400 is a measurement of validity — and under A5 that precondition fails.
When a precondition fails, neither branch of a conditional applies. The deadlock dissolves
rather than resolving, and the frozen text stays frozen and untouched.

What replaces the choice is a measurement. The limitation is not seed luck to be voted on;
it is **rank resolution**, and it is attacked directly in Phase 3.

Two observations to hold while doing it, because they cut opposite ways and both are true:

- The counted tracking is seed-stable at 0.9956 / 1.0 / 0.9868 and 0.9824 / 0.9824 /
  0.9956. Whatever else is uncertain, the counted axes do track under this driver.
- Seed-stability of the tracking does not rescue it. 1a exists because tracking under a
  monotone driver is uninformative *by construction* — the degeneracy is structural, not
  noisy, so a stable 1.0 is exactly what a degenerate instrument produces. The tracking
  being real and the tracking being interpretable are separate questions, and only the
  second is open.

I am aware that the outcome I am making more likely — DEGENERATE — is the one that
preserves three verdicts. That is why Phase 1's retroactive sweep and Phase 3's
pre-commitments both run before the number arrives, and why Phase 2 precedes Phase 3.

### A7. `grid_correlation`'s silent 0.0 gets a declared node, not a census line

You censused it and did not refactor it because it lives in the frozen M5 instrument. The
census was right; leaving it at that is not. A known defect inside a frozen instrument is a
known defect, and freezing is not a reason to stop tracking it — it is a reason it needs a
declared node with an owner decision about whether the freeze is broken.

Declare `M6-FROZEN-INSTRUMENT-DEFECT-REGISTER` with an identity. Scope: both non-rank
silent-zero instances, what each one's zero means in the frozen instrument's outputs, which
committed M5 numbers depend on them, and what breaking the freeze would cost. Do not
execute it and do not touch the frozen instrument here.

### A8. The contract repair is unblocked without N

`M6-CONTRACT-INTEGRITY-REPAIR` was waiting on N because its void lists depend on standing
verdicts. It does not need N resolved — it needs the three verdicts not voided and not
depended upon. Declare that as a constraint on the repair: it may **not void** the three
diffuse verdicts and may **not take any dependency on them** — no repair decision may be
justified by their standing. Under that constraint the repair may be sequenced regardless
of how N lands, and it stops being the reason this node must close first.

---

## PHASE 0 — RESTATE

With file and line evidence: the law at `eb20aad9698e1825` quoting 1a and 1e/1f/1g verbatim;
the frozen validity-precision declaration at `3f815d7`; `phase5_N.json` in full including
both per-pair conditionals; the counted-instrument sweep record — driver, levels, level
count, seeds, full pairwise matrix per seed, and the axis-span qualification status of every
axis at every seed; and a complete list of **every threshold comparison in the protocol that
has ever produced a committed verdict** — axis floor qualification, R5 census ceiling, 1a
validity, effect bar, clearance tolerance, every one — with the measured value, the
threshold, the margin, and whether a replicate spread for that statistic exists.

That last item is the input to Phase 2 and is the real work of Phase 0. Where no replicate
spread exists for a statistic, say so; that is a finding, not a gap to be filled by
assumption.

## PHASE 1 — THIRD AMENDMENT: 1i, MEASUREMENT ADEQUACY. DECLARED AND HASHED FIRST.

> **1i — ADEQUACY PRECONDITION.** Every comparison of a measured statistic against a
> threshold in this protocol has a precondition: the reading must be a measurement of which
> side of the threshold it falls on. It is such a measurement only if the absolute margin
> between the reading and the threshold **exceeds the replicate spread of that same
> statistic under the same instrument**, where replicate spread is measured across the
> instrument's declared seed ensemble.
>
> Where the margin does not exceed the spread, the comparison yields
> `ADEQUACY_PRECONDITION_UNMET`. This is not a verdict in either direction and may not be
> read as one. No conditional keyed on the comparison applies, because the conditional's
> precondition failed. The response is to increase resolving power and re-measure — never
> to move the threshold, never to pick the side that suits, never to commit and challenge
> afterward.
>
> Where no replicate spread has ever been measured for a statistic, the comparison is
> `ADEQUACY_UNASSESSED` until one is.
>
> Rationale, declared before the retroactive sweep: a committed verdict acquires inertia
> and everything downstream reasons from it. The cost of staying an unreproducible reading
> is a delay; the cost of committing one is a load-bearing number nobody can dislodge.
>
> **Retroactive application is mandatory and symmetric.** 1i applies to every committed
> threshold verdict in the protocol, not only to verdicts under examination, and not only
> to verdicts whose re-reading is convenient. A PASS found `ADEQUACY_PRECONDITION_UNMET` is
> re-marked exactly as a FAIL would be.

Strictly additive. Hash it, move the identity from `eb20aad9698e1825`, record old identity,
new identity, reason, authorization, and prove by mechanical diff that 0.25 / 0.80 / 2.0 /
`supporting_axes_never_count` and both prior amendments are byte-identical.

**Pre-commit the red-flag test.** If the Phase 2 retroactive sweep finds that 1i disturbs
only verdicts whose disturbance is convenient — that is, if it stays FAILs and never
unsettles a PASS — report that pattern explicitly as a suspicious result requiring
explanation, not as a clean outcome. Declare this now, before the sweep.

## PHASE 2 — RETROACTIVE ADEQUACY SWEEP. BEFORE ANY NEW MEASUREMENT.

Apply 1i to every committed threshold verdict from Phase 0's inventory. One row each:
verdict, statistic, reading, threshold, margin, replicate spread, ADEQUATE /
`ADEQUACY_PRECONDITION_UNMET` / `ADEQUACY_UNASSESSED`. Re-mark every non-adequate verdict
in place, in both directions, including verdicts I have relied on in briefs and verdicts
you have already committed as degradations.

Then run the red-flag test and report its result plainly.

Expect this phase to be uncomfortable. If it is not, check the sweep.

## PHASE 3 — RESOLVE THE COUNTED-INSTRUMENT SWEEP BY RESOLUTION, NOT BY VOTE

Pre-commit all readings before measuring:

- Attack rank resolution first: refine the counted-instrument sweep to the ~25-level
  density you identified, at the commissioned anchor seed. More levels is the correct
  remedy because the limitation is the rank statistic's resolving power at n levels, not
  seed luck.
- Then measure the replicate spread of the validity statistic across the declared seed
  ensemble at the refined density.
- Rule by 1i: margin exceeds spread → the verdict stands as measured, VALID or DEGENERATE,
  and its consequence commits per the frozen 1d and `phase5_N.json` conditionals with no
  further interpretation.
- Margin still does not exceed spread at the refined density → `ADEQUACY_PRECONDITION_UNMET`
  stands, and Phase 4 records the contingency rather than a number.

Every axis must clear its span qualification at the refined density; report how many axes
qualify and how many levels survive. If refinement changes which axes qualify, say so
before reading any rho.

## PHASE 4 — CLOSE N, OR RECORD THE CONTINGENCY HONESTLY

If Phase 3 rules: state N with the per-pair justification and commit the consequences,
including three FAILs if that is what it says.

If Phase 3 remains inadequate: N is not 3 and is not 0. The three pairs take the status
`PASS_CONTINGENT_ON_UNRESOLVED_INSTRUMENT` — strictly worse than `PASS_WITH_UNTESTED_
DRIVER`, because a named instrument whose verdict would decide them exists and could not be
read. Record the contingency, the exact number that would resolve it, and what would have to
be built to measure it. Do not let the contingency decay into a PASS through repetition in
later records: every downstream reference to these three verdicts carries the status.

Either way, apply A8: state the repair's no-void, no-dependency constraint in the repair's
own declaration so it can be sequenced now.

## PHASE 5 — DECLARE A7, VERIFY

Declare `M6-FROZEN-INSTRUMENT-DEFECT-REGISTER` with identity and scope, unexecuted.

Verification: bars byte-identical across all three amendments by diff; strict additivity of
1i confirmed against every currently-FAILing verdict; negative control on 1i — identify a
verdict whose margin genuinely exceeds its spread by a wide factor and confirm 1i passes it
untouched, since a precondition that fires on everything is not discriminating; silent-zero,
constant-vector and tie sweep across every new number; self-approval list.

## WHAT THIS NODE MAY NOT DO

Move a bar. Re-draft a frozen declaration — including the defective one at `3f815d7`, which
stays frozen and defective with the defect recorded. Delete a superseded record. Decide N by
seed vote. Execute `M6-CONTRACT-INTEGRITY-REPAIR`, `M6-MARBLING-INSTRUMENT-REPAIR`,
`M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION` or `M6-FROZEN-INSTRUMENT-DEFECT-REGISTER`. Touch the
frozen M5 instrument. Read, echo or commit `.env`.

## BOUNDARY REPORT

1i and both identities. The Phase 2 retroactive table in full, with the red-flag test result
and every verdict it disturbed in either direction. The Phase 3 refinement: axes qualifying,
levels surviving, margin, spread, ruling. N or the contingency. A7 and A8 declared. Phase 5
including failures. Then, separately, the one thing you are least confident is correct, as a
question.
