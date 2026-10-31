# M6 — ESTABLISHMENT CLOSURE

Follows `M6-MEASUREMENT-ADEQUACY` (`8f6cb81` → `af6864d`), law at `3586022acc972aff`.
Owner authorization: transmission of this brief authorizes Section A and the fourth
amendment. Object rather than execute if any of it is wrong.

---

## SECTION A — OWNER RULINGS

### A9. `ADEQUACY_UNASSESSED` suspends. The burden falls on the affirmative claim.

You asked whether an unassessed comparison keeps operating as a verdict while its spread
awaits measurement, or whether the precondition's logic suspends it exactly as `UNMET` does.

Ruling: **it suspends.** 1i's operative sentence requires that the reading be a measurement
of which side of the threshold it falls on, and that requires `margin > spread`. Where
spread is unknown, `margin > spread` cannot be asserted. The verdict was never established.
An unassessed PASS is a property declared with nothing capable of noticing whether it holds
— that is `DECLARED_BUT_UNREALIZED`, one level up, applied to the protocol instead of to an
artifact. It does not get an exemption for being ours.

`UNMET` and `UNASSESSED` differ in remedy, not in force. Rename to keep them from being
conflated in later records:

- `ADEQUACY_PRECONDITION_UNMET` — spread measured, margin does not exceed it. Positive
  evidence the instrument cannot decide at current resolution. Remedy: resolving power.
  May prove unresolvable.
- `NOT_ESTABLISHED_PENDING_SPREAD` — spread never measured. No evidence either way.
  Remedy: measure it. Bounded, known work.

Neither may be relied upon. Neither is a FAIL.

### A10. The asymmetry, and why it is principled rather than convenient

You correctly saw that a blanket reading suspends the marbling FAIL and every floor
ineligibility exclusion alongside the PASSes. It must not, and the reason is one rule
applied uniformly rather than three exceptions:

> **The burden of establishment falls on the affirmative claim.** Adequacy failure removes
> inferential license. Which verdict that removal disturbs depends on which side of the
> comparison was asserting something.

Applied, with no case decided by its convenience:

- **Unassessed PASS** — asserts a bar was cleared. Suspends to
  `NOT_ESTABLISHED_PENDING_SPREAD`. May not be relied upon by any downstream node.
- **Unassessed FAIL** — asserted nothing; it refused to certify. Absence of adequate
  evidence still leaves the thing uncertified. The FAIL stands, re-marked as *not
  certified, adequacy unassessed* rather than as *measured to fail*. The distinction
  matters when someone later tries to treat the FAIL as a measured fact.
- **Unassessed ineligibility exclusion** — keeps the axis out. To *use* an axis requires
  positive evidence it is eligible; that evidence is what is missing.
  `EDGE_HIGHLIGHT_RESPONSE` does not become available because the evidence that it is too
  noisy is itself unassessed.
- **Unassessed degeneracy verdict** (the A2 no-FAIL margin) — degeneracy is a refusal to
  extract information. It stands, and the sweep continues to carry nothing.

Note the shape of the result: nothing is rescued, several things are weakened, and the one
verdict that would have been convenient to revive stays dead. If your execution of this
rule produces a rescue anywhere, that is a signal you have applied it wrongly — report the
case rather than committing it.

### A11. Before measuring anything — the 26 may largely discharge from committed records

I believe R4's `separation_margin = 2.0` is structurally an adequacy rule under a different
name, and that if I am right, most of the 26 unassessed rows discharge analytically without
a single new render.

The argument, to be verified or refuted rather than adopted:
`axis_noise_floors.json` records `max_seed_only_effect` per axis — the effect statistic
computed between same-family seed variants. That is the null distribution of the clearing
statistic: what the instrument reports when nothing but the seed differs. It is therefore a
replicate spread of the very statistic the clearing comparison uses. The standing
requirement `required_clearing_effect = max(0.25, 2 × floor)` then implies
`clearing − floor ≥ floor = spread` for every floor-limited axis, which is 1i's condition
against the floor-derived threshold. For axes where the 0.25 bar dominates, the spreads are
small (0.00651 to 0.00886 on several) and the margin will clear them easily — but that must
be checked per row, not waved through.

Where I may be wrong, and what you must test rather than assume:

1. Whether `max_seed_only_effect` is the spread of the *same* statistic as the clearing
   comparison, or of a related one. If the statistics differ, the transfer is invalid.
2. Whether a spread measured on POWDER_MATTE transfers to a cross-family comparison on
   other families. It may not. If you use it, declare the transfer as a method with stated
   validity conditions — same instrument, same statistic, and the spread taken as the
   conservative maximum across every family in the comparison where more than one is
   available — and mark rows discharged by transfer distinctly from rows discharged by
   direct measurement.
3. Whether `max` or `mean` seed-only effect is the correct spread estimator here. Use the
   conservative one and say why.

If the argument holds, record it plainly: the protocol was less naked than Phase 2 made it
look, and R4 was doing adequacy work under another name the whole time. If it fails, record
that too — it is a cleaner finding than the comfortable one.

### A12. N, and the schedule

N = 3 becomes: **three verdicts that must not be voided, none of them established.** That
reads worse than it is, because A8 already released `M6-CONTRACT-INTEGRITY-REPAIR` under a
no-void, no-dependency constraint. Nothing that was moving stops. Confirm in the repair's
declaration that "not established" satisfies "no dependency" — the repair may not justify
any decision by these verdicts' standing, and now there is no standing to justify by.

---

## PHASE 0 — RESTATE

`measurement_adequacy/phase2_retroactive.json` in full, all 31 rows, each classified by
which side of its comparison carried the affirmative claim. The 1i text verbatim. The
statuses of the three diffuse, both flake, both raking and the glitter PASS. The exact
statistic used in each of the 26 unassessed comparisons, named precisely enough to tell
whether `max_seed_only_effect` is a spread of that same statistic. `axis_noise_floors.json`
in full. Which retained frames and seed ensembles already exist on disk, per family.

## PHASE 1 — FOURTH AMENDMENT: 1j, BURDEN OF ESTABLISHMENT

Hash A9's status split and A10's burden rule into the law. Strictly additive. Move the
identity from `3586022acc972aff`; prove by mechanical diff that PASS_LAW and all three
prior amendments are byte-identical.

Include the self-check: **an application of 1j that rescues anything is misapplied.**
Pre-commit that any rescue encountered is reported, not committed.

## PHASE 2 — ANALYTIC DISCHARGE (A11). NO RENDERS.

Test my argument. Per unassessed row: the comparison, its statistic, whether a spread for
that statistic exists in committed records, the discharge route (DIRECT / TRANSFERRED /
NONE), the margin, the spread, the verdict. Declare the transfer method and its validity
conditions before applying it. Report how many of the 26 discharge, how many by transfer,
and how many remain.

If my argument fails, say so in one sentence and move to Phase 3 with all 26 standing.

## PHASE 3 — MEASURE WHAT REMAINS, CHEAPEST FIRST

For rows not discharged: measure the replicate spread. Recompute from retained frames
wherever possible; render only where nothing on disk can produce the number, and say which
is which. Order by cost ascending and report a running count, so the work can be stopped
and resumed at a boundary if a session is interrupted.

Any row whose spread measurement is itself expensive enough to need its own node: name it,
do not start it.

## PHASE 4 — RE-RULE, AND PUBLISH THE ESTABLISHMENT TABLE

One table, every threshold verdict in the protocol: verdict, affirmative side, statistic,
reading, threshold, margin, spread, source of spread, and final status — ESTABLISHED /
`NOT_ESTABLISHED_PENDING_SPREAD` / `ADEQUACY_PRECONDITION_UNMET` / stands-uncertified.
This table becomes the thing any downstream node consults instead of the verdict records
themselves. Every reference to a verdict elsewhere in the repository carries its status.

Confirm A12 in the repair's declaration.

## PHASE 5 — RECORD THE FINDING AT THE TOP LEVEL

Whatever Phase 2 concludes, the finding belongs in the programme record and not buried in
an M6 subfolder: **the protocol compared statistics to thresholds without measuring most of
those statistics' reproducibility, and did not notice until an adequacy precondition was
written for an unrelated reason.** State how long it ran that way, how many verdicts were
affected, how many discharged analytically, and what now prevents recurrence.

If A11 holds and R4 was already enforcing adequacy for a subset, say that in the same
paragraph — the finding is that the protection was partial and unnamed, not that it was
absent. Do not let the good news soften the statement, and do not let the bad news suppress
the good news.

## PHASE 6 — VERIFY

Bars byte-identical across four amendments. 1j strictly additive. Rescue check: enumerate
every verdict 1j touched and confirm none improved. Negative control on the transfer method
if used: a case where transfer is invalid must be shown to be rejected by the stated
conditions. Silent-zero, constant-vector and tie sweep on every new number. Self-approval
list.

## WHAT THIS NODE MAY NOT DO

Move a bar. Re-draft a frozen declaration. Delete a superseded record. Rescue a verdict.
Execute `M6-CONTRACT-INTEGRITY-REPAIR`, `M6-MARBLING-INSTRUMENT-REPAIR`,
`M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION` or `M6-FROZEN-INSTRUMENT-DEFECT-REGISTER`. Touch
the frozen M5 instrument. Read, echo or commit `.env`.

## BOUNDARY REPORT

1j and both identities. The A11 verdict — did the R4 argument hold, and how many rows
discharged by which route. The establishment table. What remains unmeasured and what it
would cost. The Phase 5 top-level record. Phase 6 including failures. Then, separately, the
one thing you are least confident is correct, as a question.
