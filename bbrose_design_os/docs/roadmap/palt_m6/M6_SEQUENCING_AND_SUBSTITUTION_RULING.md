# M6 — SEQUENCING RULING AND SUBSTITUTION PRE-COMMITMENT

Follows `M6-ESTABLISHMENT-CLOSURE` (`842132d` → `d4e8338`), law at `3eb1a9b0fe36bfe4`.
Owner rulings on the escalated satisfiability question and on the ordering of the seven
queued nodes. Object rather than execute if any of it is wrong.

---

## SECTION A — RULINGS

### A13. The two SHEEN UNMETs are `UNMET_BY_CONSERVATIVE_PROXY`. The satisfiability
question is correct but premature.

1i's operative text asks for "the replicate spread of that same statistic under the same
instrument, measured across the instrument's declared seed ensemble." For a cross-family
clearing, that quantity is: **the cross-family clearing itself, recomputed at each seed of
the declared ensemble, and its dispersion.**

What was used is `max_seed_only_effect` — the same functional evaluated at the null point,
where no real family difference exists. It is the magnitude of the instrument's response to
nothing. That is a legitimate *proxy* and a conservative one, and A11's transfer method was
right to use it in the absence of anything better. It is not the named quantity, because
the dispersion of a non-null estimate is not the magnitude of the null.

Ruling: re-mark both SHEEN legs and the flake PATTERN leg `UNMET_BY_CONSERVATIVE_PROXY`,
with the proxy named and the direct quantity named alongside it. This is not a softening —
they remain unestablished, they remain unusable, and the burden rule still suspends the
pairs. It is a correction of *what has been shown*: we have shown they fail a conservative
surrogate, not that they fail the test.

Correct also the framing in your report: "the only other eligible lobe axis (FWHM) is
rho-1.0 with SHEEN under R5 and may not join." That collapses three distinct properties:

- **floor-eligible** — FWHM, PEAK, SPECULAR, GRAZING and SHEEN all are; EDGE is not.
- **R5-permitted for this pair** — R5 bars two above-ceiling axes from *both* counting
  toward one pair. FWHM is barred from counting alongside SHEEN. In SHEEN's absence it is
  not barred at all; FWHM|GRANULARITY reads 0.1905 on the N=8 census. PEAK, SPECULAR and
  GRAZING against GRANULARITY are likewise under the ceiling.
- **clears its bar on this pair** — unmeasured for most of them.

Report all three per candidate axis before concluding anything is unavailable. I suspect
what you meant is that FWHM is the only other axis that *clears* on these pairs, which is a
different and much more interesting claim — and one that is measured, not inferred.

### A14. Substitution is legitimate, and is pre-committed now rather than after the number

If the direct ensemble measurement confirms UNMET, a pair may look for a different second
axis. That is not inventing a rescue: these axes were commissioned, floor-eligible and
declared long before this failure. But it becomes cherry-picking the moment candidates are
chosen after their effects are seen. So it is fixed now:

> For each affected pair, **name every candidate axis before measuring any of them** —
> every axis that is floor-eligible and R5-permitted alongside the pair's surviving counted
> axis. Measure all of them. Report all of their effects and adequacies, not only the one
> that succeeds. A pair passes on a substitute only if that substitute clears its own bar
> with margin exceeding its own directly-measured ensemble spread.
>
> If no candidate qualifies, the pair **FAILS** and is recorded as FAIL. Separately and
> additionally, record the finding that the two-axis law is unsatisfiable for that pair on
> the commissioned instrument suite. That is a fact about the instruments, not a reason to
> weaken the law. The law does not bend to fit the rig; the rig is what gets extended, in a
> declared commissioning, if anyone later chooses to.

Your satisfiability question is thereby answered in its proper order: it is live only after
A13's direct measurement, and if it goes live, the above is what happens.

### A15. Your strict declared-ensemble ruling stands and is adopted

"Partial 2-seed estimates record progress but never establish" — correct, adopted, and
worth stating as general law rather than a node-local judgment: **a partial replicate is
evidence about progress, never about establishment.** This node exists because
under-measured statistics were the defect; it cannot close by committing one. Hash it with
1j's family on the next amendment rather than leaving it as your local ruling.

### A16. The calendar correction is accepted and is worse than my version

"Months" was wrong. Two days, two protocol generations, and every verdict the protocol ever
produced is the accurate statement, and it is more damning, not less — the unprotected span
was total. Keep your wording. That you corrected my brief in the direction that reflects
worse on the programme is the behaviour the finding file exists to protect.

---

## SECTION B — SEQUENCING RULING

### The ordering constraint that decides everything

`M6-CONTRACT-INTEGRITY-REPAIR` makes 40 dead declared parameters live and reconciles 25
under-declared builder constants. Its VALUE_MOVING half **changes what the renderer
produces**. Every render-derived statistic measured before it — every ensemble spread,
every census replicate, every clearing — is therefore measured on an engine that is about to
change, and would have to be re-measured after.

The three measurement nodes total roughly 100 to 130 renders. Spending them first would be
spending them twice.

There is a second and larger reason. An engine in which 48% of declared parameters never
reach the render is not the engine anyone intends to ship. Verdicts about it — including
their reproducibility — characterise an artifact that is not the product. Measuring the
reproducibility of the wrong artifact very precisely is not progress.

### Ruled order

1. **`M6-CONTRACT-INTEGRITY-REPAIR`** (`b862941c303588f9`) — first, both halves, under the
   constraints in Section C. Render-light relative to the measurement nodes and it gates
   all of them.
2. **`M6-MARBLING-INSTRUMENT-REPAIR`** (`04374a1057977dd1`) — second. Its diagnosis was that
   `×0.55` preserves R:G:B exactly, making the marble luminance-only; that is a derivation-
   coefficient defect and sits inside the contract repair's subject matter. Running it
   before the contract repair would fix the same class twice.
3. **`M6-DECLARED-ENSEMBLE-SPREADS`** and **`M6-CENSUS-REPLICATE`** — third, and
   **planned together before either runs**. Same families, same declared seed ensembles,
   overlapping render sets. Produce a combined render manifest first and report how many of
   the ~86 to 102 renders are shared; I expect meaningful overlap and want it exploited
   rather than discovered afterwards.
4. **`M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION`** (`31b04a6c1eff8de2`) — fourth. Also
   render-heavy; check its manifest against (3)'s for shared frames before rendering.
5. **`M6-FLOOR-STATISTIC-REPLICATE`** — last of the measurement work. Expensive, and the
   burden rule means delay costs nothing: the exclusions stand while it waits, and no axis
   becomes usable by its absence.
6. **`M6-FROZEN-INSTRUMENT-DEFECT-REGISTER`** (`ce4124969cf7396c`) — a documentation and
   decision node with no render cost. Slot it wherever a render queue is occupying the
   machine; it does not need its own place in the queue.

### What this ordering costs, stated plainly

Established rows in the establishment table may need re-establishing after the repair. The
one fully-established pair PASS, `PRESSED_VS_BAKED`, is among them. That cost is real and I
am accepting it, because the alternative is establishing verdicts about an engine we are
about to change.

---

## SECTION C — CONSTRAINTS ON THE CONTRACT REPAIR

Read its own declaration first; these are additions, not replacements.

1. **A8/A12 unchanged.** No void of the three diffuse verdicts, no dependency on them. There
   is now no standing to depend on, which satisfies the constraint trivially — confirm it
   rather than assume it.
2. **Record pre-repair values for everything.** Before any VALUE_MOVING change, snapshot
   every committed statistic the repair could move, with its current value. The snapshot is
   the baseline against which post-repair movement is read.
3. **Re-adjudication obligation, declared before the repair runs.** Every verdict and every
   establishment-table row is carried forward and re-adjudicated on the repaired engine,
   with pre- and post-repair values recorded side by side. No verdict survives the repair by
   inertia.
4. **The anti-reroll guard.** A verdict that *improves* after the repair must be explainable
   by a **named parameter whose realization changed**, traceable to a specific entry in the
   dead-parameter or under-declared census. An improvement that cannot be attributed to a
   named realization change is not a repair effect; it is an unexplained movement, and it is
   reported as such rather than banked. Declare this before the repair, because "repair the
   engine and re-measure" is otherwise indistinguishable from re-rolling the dice.
5. **VALUE_PRESERVING and VALUE_MOVING stay strictly separated**, per your own standing
   design rule: bit-identity provable for the former with nothing voided, an explicit void
   list per item for the latter. Commit them as separate commits so the boundary is legible
   in history.
6. **The marble coefficients** must become genuinely chromatic as part of the under-declared
   reconciliation, not left as a luminance-preserving scalar with a new name. Reconciling a
   constant into the contract while leaving it physically wrong is declaration theatre.

---

## SECTION D — NEXT AMENDMENT (fold into the repair node, hashed before it acts)

- A13's `UNMET_BY_CONSERVATIVE_PROXY` status, with proxy and direct quantity both named.
- A14's substitution rule.
- A15's partial-replicate law.

Strictly additive, bars byte-identical, identity moved from `3eb1a9b0fe36bfe4`, chain
recorded.

## WHAT MAY NOT HAPPEN

No bar moves. No frozen declaration is re-drafted. No verdict is rescued. No measurement
node starts before the contract repair lands. The frozen M5 instrument stays untouched.
`.env` is not read, echoed or committed.
