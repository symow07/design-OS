# M6 — DRIVER COMPLETENESS AND STIMULUS ADEQUACY

Follows `M6-INDEPENDENCE-AMENDMENT` (commits `e464d65` → `787d932` → `a6f2d20` → `63bb0a9`),
which moved the protocol identity to `f2438bcae8b86533`.

Owner authorization: transmission of this brief is the authorization for the four rulings
in Section A and the second amendment in Phase 1. As before — if you conclude any of it is
wrong, stop and say so rather than executing a version you do not believe.

N = 3 is **not banked** by this brief. It is held provisional until Phases 2 through 4
close, because two items in your boundary report can move it and one of them can move it
to 0.

---

## SECTION A — OWNER RULINGS ON THE ITEMS YOU PLACED

### A1. The raking un-voiding — ruled, and it grants nothing

You are correct that the raking void rested on a degenerate reading whose one leg was a
Spearman against a bit-constant vector. A correlation against a constant vector is not
1.0; it is **undefined**. That is a computational defect, not a measurement, and a verdict
built on it has no evidentiary basis.

Ruling: the VOID is superseded in place — its evidence is withdrawn. Raking is **not**
thereby restored to eligibility. It returns to `NOT_COMMISSIONED_AS_INDEPENDENT_CHANNEL`:
neither voided nor available. Before raking may be counted toward any pair anywhere, it
requires its own declared commissioning with measured noise floors, negative controls and
realization gates, exactly as any new instrument would.

Consequence to record explicitly: **this improvement improves nothing.** No verdict flips,
no pair gains a channel, nothing that was FAIL becomes PASS. The `AMENDMENT_INDUCED_
IMPROVEMENT` hold is discharged by ruling rather than by commitment, and the amendment is
demonstrated not to have functioned as a rescue vehicle. Record that demonstration — it is
the evidence that 1c did its job.

Separately: audit for the constant-vector defect **everywhere**, not only here. Any
Spearman computed in this project against a vector with zero variance is an artifact. Add
a guard that raises rather than returning a number. This defect class — a computation that
silently returns a plausible value when its input is degenerate — is now the third of its
kind after the N=4 census degeneracy and the silent-zero floor. Per the standing rule, a
third appearance gets a structural guard, not a fix. Declare the guard, name the class,
and make it impossible to compute an unguarded rank correlation anywhere in the codebase.

### A2. `compression_texture_amplitude` — this is the highest-stakes open item and you did
not adjudicate it

You reported, unsoftened, that it "reproduces the micronormal lockstep exactly (counted
axes 1.0, n=11, all qualifying — a second relief-class driver)." You reported it under
Phase 5 findings rather than ruling on it in Phase 4. **All qualifying** is the phrase that
matters: it means this sweep is not disqualified by the floor filter the way micronormal's
levels were, and it therefore may not inherit micronormal's dismissal.

Two questions must be answered explicitly and in this order, before anything else in this
node:

1. Is the `compression_texture_amplitude` sweep **VALID or DEGENERATE under 1a** — does its
   full pairwise matrix contain at least one pair at or below 0.80? You listed three VALID
   sweeps and it was not among them; state whether that is because it was measured
   degenerate or because it was never assessed.
2. Does `compression_texture_amplitude` **differ between the two families** of any of the
   three diffuse pairs — by value or by block presence, the same test you applied to
   micronormal?

If both answers are yes for a pair, then per the hashed 1d that pair **FAILS**. It gets no
second argument and no substitute channel; raking is not available to it under A1. Rule it
and commit it as a degradation. If you find yourself reaching for a reason this case is
different from the micronormal case, stop and write down the reason before acting on it,
so it can be checked rather than absorbed.

### A3. The 0.0078 near-miss on GRANULARITY under grain-scale — resolve by precision, never
by bar

A qualification decided by 0.0078 is decided by noise, and it is currently discharging a
driver — that is, a near-miss is being used to conclude `NOT_COMMON_DRIVER`, which is a
null result carrying a safety condition. That is fragile in exactly the direction that
matters.

Ruling: the bar does not move. Record `MARGINAL_NON_QUALIFYING` with the margin stated,
and resolve it by adding precision — more seeds, more levels, or both, on the existing rig
— until the verdict is decided by a margin larger than the seed-only spread of the same
statistic. If added precision moves it to qualifying, adjudicate it as a real driver and
accept the consequence. Declare before re-measuring which way each outcome will be read.

### A4. The flake independence discharge — re-mark first, diagnose second

You reported that 8 of 10 original flake `MEASURED_DIVERGENT` pairs rest on sub-floor
variation and that `metallic_response` is degenerate. Those divergences are what discharged
`PASS_PENDING_INDEPENDENCE` into committed PASSes on the reflective pairs.

Ruling: those PASSes are **re-marked back to `PASS_PENDING_INDEPENDENCE` immediately**,
in this node, before any diagnostic runs. A PASS whose supporting evidence has been shown
possibly invalid does not keep its status while the investigation is scheduled. Mark first,
diagnose second — the reverse order lets an unsupported PASS sit in the record for the
duration of the investigation, which is the same failure the whole `DECLARED_BUT_
UNREALIZED` class is about.

Declare `M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION` as a node with its own identity, scope it
(driver tables per reflective pair under the amended law, sweep validity under 1a, floor
qualification per level), and sequence it — but do not execute it here.

---

## PHASE 0 — RESTATE. NO EDITS, NO MEASUREMENTS.

Restate into the node record, with file and line evidence:

1. The amended law at `f2438bcae8b86533`, quoting 1a, 1b, 1c, 1d verbatim.
2. `independence_drivers_phase2.json` and `..._phase4.json` in full: for each of the three
   diffuse pairs — the two counted axes, each axis's measured inter-family effect, the
   census |rho|, the complete driver table with classification, and for every driver
   recorded `NOT_COMMON_DRIVER`, the swept range and the measured span of each counted axis
   over it.
3. For every driver in every table: **the two families' actual values of that parameter**
   for that pair. If a parameter is absent by block presence rather than differing by
   value, say so and say what the absent block's effective value is in the render.
4. The `axis_span_qualification` rule as operationalized, and the negative-control run that
   selected it over per-level gating.
5. The `compression_texture_amplitude` sweep record in full, including its pairwise matrix
   if retained.

Exit condition: item 3 is complete for every driver in every table. This node cannot run
without it, and its absence is the reason the Phase-4 conclusions are currently
unfalsifiable.

---

## PHASE 1 — SECOND AMENDMENT. DECLARED AND HASHED BEFORE ANY PHASE-2 NUMBER.

Strictly additive again. No bar moves. Diff and prove it, do not assert it.

### 1e — CONTAINMENT: what makes a `NOT_COMMON_DRIVER` reading valid

> A `NOT_COMMON_DRIVER` conclusion — reached because a counted axis's response to a driver
> falls under its qualification threshold — is valid **only if the swept range contains the
> interval between the two families' declared values of that driver for that pair.**
>
> If the swept range contains the inter-family interval, the reading stands: the axis does
> not vary between these two families under this driver, which is the only question the
> driver condition asks. A wider sweep is not required and does not strengthen it, because
> a wider sweep measures products that do not exist.
>
> If the swept range does not contain the inter-family interval — narrower, offset, or on
> the wrong side of it — the reading is `UNTESTED_AT_SEPARATING_STIMULUS`, not
> `NOT_COMMON_DRIVER`, and the driver must be re-swept over at least the containing
> interval before the pair may be ruled.
>
> Where a parameter differs by block presence rather than by value, the interval runs from
> the block-absent effective value to the block-present value, and the sweep must span it.

The criterion is containment, not width. This is checkable geometry, not judgment.

### 1f — CONSERVATION: the positive control that makes a null result mean something

> For each pair and each counted axis, the axis's measured inter-family effect must be
> accountable by the union of the swept drivers' measured spans over their inter-family
> intervals. If the pair's measured effect on an axis materially exceeds what every
> enumerated driver can produce across the interval that actually separates the families,
> the **driver enumeration is proven incomplete**, and the residual must be named — as a
> specific parameter, a specific builder constant, or as `UNACCOUNTED_CAUSE` if it cannot
> be identified.
>
> A pair carrying an `UNACCOUNTED_CAUSE` residual may not be recorded as a clean PASS. Its
> honest status is `PASS_WITH_UNTESTED_DRIVER` with the residual magnitude stated, because
> an unenumerated cause is by definition an untested driver.
>
> Rationale, declared before the numbers: `NOT_COMMON_DRIVER` is a null result discharging
> a safety condition. This project has been wrong three times in exactly that pattern — the
> sub-pixel zero used to prove a distinction, the silent zero on `RAKING_SHADOW_FRACTION`,
> and the constant-vector rank correlation. Conservation is the positive control that
> converts "we found nothing" into a bounded claim about how much there was to find.

### 1g — Structural guard on degenerate statistics

Per A1: no rank correlation may be computed in this codebase against a zero-variance
vector. The guard raises. Declare the defect class by name, register it alongside
`DECLARED_BUT_UNREALIZED` and `BUILDER_CONSTANT`, and make the guard the only path by
which a correlation can be computed.

Hash the amended law. Move the identity from `f2438bcae8b86533`. Record old identity, new
identity, reason, owner authorization, and the mechanical diff proving 0.25 / 0.80 / 2.0 /
`supporting_axes_never_count` byte-identical.

### 1h — Pre-commit the readings

Before Phase 2:

- `compression_texture_amplitude` VALID **and** differing for a pair → that pair FAILS,
  committed, no substitute channel.
- Any `NOT_COMMON_DRIVER` whose sweep fails containment → re-swept; if the counted axes
  then track above 0.80 on a VALID sweep, that pair FAILS.
- Conservation violated for a pair → residual named; pair stays `PASS_WITH_UNTESTED_
  DRIVER` with the residual on the record, and the fencing statement is upgraded from
  "no declared driver tracks" to "the declared drivers cannot account for the separation;
  the residual is X."
- Conservation satisfied and containment clean for a pair → that pair's fencing is
  builder-constants-only, as currently recorded, and now for a demonstrated reason rather
  than an unexamined one.

---

## PHASE 2 — ADJUDICATE `compression_texture_amplitude` (A2). FIRST. ALONE.

Answer A2's two questions, rule, and commit before touching anything else. If a pair FAILS
here, say so before proceeding, because it changes what the rest of the node is for.

## PHASE 3 — CONTAINMENT AUDIT (1e)

Every `NOT_COMMON_DRIVER` in `phase4.json`, one row each: driver, pair, family A value,
family B value, inter-family interval, swept range, CONTAINS / DOES_NOT_CONTAIN. Re-sweep
every DOES_NOT_CONTAIN over at least the containing interval. Start with SHEEN under
`sheen_response.sheen`, since it is the case you raised.

## PHASE 4 — CONSERVATION CHECK (1f)

Per pair, per counted axis: measured inter-family effect; the span each enumerated driver
produces on that axis over its inter-family interval; the union; the residual. State
whether conservation holds. Where it does not, name the residual.

My prediction, recorded so it can be wrong: MATTE_VS_SATIN will violate conservation on
SHEEN — a ≥0.331 inter-family effect against a best-driver span of 0.221 — and the residual
will land on the non-sweepable builder constants you already fenced. If that is what you
find, your committed verdict was right and under-argued, and it gets stronger. If you find
otherwise, report it against this prediction plainly.

## PHASE 5 — RE-RULE N

Re-state the three diffuse pairs under the twice-amended law. Then: **N = _**, with the
one-line justification per pair. This is the number `M6-CONTRACT-INTEGRITY-REPAIR` binds to.

## PHASE 6 — EXECUTE A1 AND A4

Supersede the raking void in place; set `NOT_COMMISSIONED_AS_INDEPENDENT_CHANNEL`; record
that the improvement improves nothing; install the 1g guard; sweep the codebase for other
constant-vector correlations. Re-mark the reflective PASSes to `PASS_PENDING_INDEPENDENCE`
and declare `M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION` with identity and scope, unexecuted.

## PHASE 7 — VERIFY, ADVERSARIALLY

Bar audit by diff. Strict-additivity check: enumerate every currently-FAILing pair and
confirm none passes because of 1e/1f/1g. Negative control on 1f: identify a case where a
driver IS known to account for an axis's inter-family effect and confirm conservation
closes there — if conservation never closes anywhere, the check is not discriminating and
must be reported as such. Silent-zero and constant-vector sweep across every new number.
Self-approval list.

---

## WHAT THIS NODE MAY NOT DO

Move a bar. Delete a superseded record. Invent a channel to rescue a verdict. Commit an
amendment-induced improvement without owner ruling. Start `M6-CONTRACT-INTEGRITY-REPAIR`
(`b862941c303588f9`), `M6-MARBLING-INSTRUMENT-REPAIR` (`04374a1057977dd1`) or
`M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION`. Re-render anything that can be recomputed from
retained frames.

## BOUNDARY REPORT

The A2 ruling and what it cost. The containment table. The conservation table and whether
my prediction held. N with per-pair justification. A1 and A4 executed, with the guard's
codebase sweep results. Phase 7 including failures. Then, separately: the single thing you
are least confident is correct, as a question.
