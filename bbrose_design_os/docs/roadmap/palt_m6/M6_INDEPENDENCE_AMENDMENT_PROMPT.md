# M6 — INDEPENDENCE ADJUDICATION AND R5 AMENDMENT

Node identity to be declared at Phase 1. Owner authorization: the transmission of this
brief by the owner IS the authorization for the amendment described in Phase 1. You are
not amending the protocol unilaterally; you are executing an owner-declared amendment.
Record it that way. If at any phase you conclude the amendment as written is wrong,
STOP and say so rather than executing a version of it you do not believe.

---

## WHY THIS NODE EXISTS

You measured two independence numbers for the same axis pair and they disagree:

- census Spearman, N=8 family census: `GRANULARITY_INDEX | SHEEN_REGION_RESPONSE` = 0.3571
- sweep Spearman, 12 levels of `micronormal_amplitude` within one family: same pair = 1.0

You correctly declined to let my pre-attached fatal reading of the second number amend
the hashed R5 definition by side-declaration. That refusal was right and is recorded as
your judgment, not as an obstruction.

The adjudication below rests on two claims, and you are to test both rather than accept
either.

**Claim 1 — the sweep instrument may be degenerate.** Spearman rank correlation between
two axes measured along a single monotone driver is 1.0 by construction whenever both
axes respond monotonically to that driver, whether or not they are the same instrument.
Monotone response to a monotone stimulus is not evidence of shared physics; it is
arithmetic. The flake_density sweep was informative precisely because 9 of 10 pairs came
back MEASURED_DIVERGENT — divergence in the matrix is what demonstrates the instrument
can distinguish anything at all. The micronormal_amplitude sweep's full matrix has not
been placed on the record. If that matrix contains no divergent pair, the sweep is
degenerate under that driver, the 1.0 carries no information, and it may not be used to
disturb anything. This is the same defect class as the N=4 census degeneracy already
documented in `axis_independence_matrix.json` — a statistic whose attainable range under
the design collapses to the value being read.

**Claim 2 — blanket driver-decorrelation is not a well-formed law.** It has no closure
over the space of drivers: for any two monotone axes a driver can be constructed under
which they track. A rule that can be made to fail everything by choice of driver is not
a rule. The defensible form is conjunctive and pair-specific, and it is stated in Phase 1.

---

## PHASE 0 — READ AND RESTATE. NO DECISIONS, NO EDITS, NO MEASUREMENTS.

Read and restate in your own words, into the node record:

1. `PASS_LAW` as currently hashed, and the current R5 definition of independence, quoting
   the exact text and the protocol identity `087c7f64317910fb`.
2. `docs/roadmap/palt_m6/axis_independence_matrix.json` in full, including the
   `census_size_caveat` and `SCHEDULED_OBLIGATION` blocks, and the superseded
   pre-commitment inside it.
3. `docs/roadmap/palt_m6/axis_noise_floors.json` — every floor and every eligibility flag.
4. `diffuse_pairs_standing.json` — for each of the three diffuse pairs, name the pair, the
   two counted axes, the measured effect for each, and the instrument each axis is read on.
5. The commissioning record of the micronormal_amplitude sweep: driver name, level values,
   number of levels, family held fixed, seeds, rig used, and — this is the item that
   matters — **the complete pairwise |rho| matrix over every axis measured in that sweep**,
   not only the pair that alarmed. If the full matrix was not retained, say so plainly.
6. The sweep record that voided the raking third channel at |rho| = 1.0, including which
   driver it was run under.
7. The realization registry (`NOT_REALIZED_IN_RENDER`) and the under-declared /
   builder-constant census, both of which Phase 2 depends on.

Phase 0 exit condition: every one of the seven items is restated with file path and line
evidence. If any is missing from the repository, record it as MISSING and name what would
have to be measured to obtain it. Do not proceed to Phase 1 with a MISSING item silently
carried.

---

## PHASE 1 — DECLARE THE AMENDMENT. BEFORE ANY NEW NUMBER IS LOOKED AT.

Nothing in this phase is permitted to consult a measurement produced after Phase 0. The
amendment is declared, hashed, and committed first, so that no reading of it can be
tuned to a result.

### 1a. The sweep instrument gains a validity condition

Declare, as a property of the sweep instrument and not of any pair:

> A sweep over a single driver is VALID as an independence instrument only if its pairwise
> |rho| matrix contains at least one pair reading at or below the R5 ceiling of 0.80. A
> sweep in which every measured pair tracks above the ceiling is recorded as
> `SWEEP_DEGENERATE_UNDER_DRIVER` and yields no independence evidence in either direction
> — it may not be used to disturb a verdict, and it may not be used to support one.
>
> Rationale, declared before the matrix is read: rank correlation along a monotone driver
> is 1.0 by construction for any two monotonically-responding axes. Divergence somewhere
> in the matrix is the only demonstration that the instrument resolves difference rather
> than restating the driver's own ordering. This is the sweep-space analogue of the
> documented N=4 census degeneracy.

This condition is symmetric and was declared before the micronormal matrix was inspected.
It can void the number that threatens three verdicts and it can equally void a number that
would have rescued one. Record that symmetry explicitly.

### 1b. The R5 independence law becomes conjunctive and pair-specific

Supersede the current R5 definition **in place** — do not delete it — with:

> Two axes may both count toward one pair's two-axis requirement only if **both** hold:
>
> **(i) CENSUS CONDITION** — unchanged, unmoved, not reinterpreted. |rho| across the
> family census is at or below 0.80, subject to the recorded census-size caveat.
>
> **(ii) DRIVER CONDITION** — for every parameter that (a) is declared in the contract or
> is a builder constant proven to reach the render, (b) is proven REALIZED in the render
> rather than listed NEVER_ARRIVES, and (c) **actually differs in value between the two
> families of this specific pair**, a sweep of that parameter on the rig carrying the
> counted axes must not show the two counted axes tracking above 0.80 — provided that
> sweep is VALID under 1a.
>
> A parameter that does not differ between the pair's two families is not a driver for
> that pair and its sweep is irrelevant to it. A parameter that differs but cannot be
> swept — categorical, structural, or otherwise not continuously variable — is recorded
> as `NON_SWEEPABLE_DRIVER`; the pair is then not a clean PASS but
> `PASS_WITH_UNTESTED_DRIVER`, entered on the standing obligations list with the driver
> named. It is not a FAIL: no evidence of tracking exists. It is not clean: the check
> could not be run.

Note what this does to the scope of the law: it is strictly additive. It removes no
condition. No pair that fails today can pass because of it.

### 1c. The raking third-channel void is re-examined symmetrically

The raking channel was voided because it tracked GRANULARITY at |rho| = 1.0 **under the
relief driver**. Under the amended law that finding is pair-specific: it disqualifies
raking as a second channel for pairs whose families differ in relief, and says nothing
about pairs whose families do not. Declare now, before knowing which pairs those are:

> The raking void is re-scoped from blanket to pair-specific by the same amendment that
> re-scopes the diffuse threat. Any verdict that IMPROVES as a consequence — a FAIL
> becoming a PASS, or a fenced provisional becoming clean — is **not** committed. It is
> recorded as `AMENDMENT_INDUCED_IMPROVEMENT`, held, and placed with the owner. Verdicts
> that DEGRADE are committed immediately without owner review.
>
> Rationale: an amendment that can only help is a rescue vehicle. This asymmetry in
> handling is what prevents it from becoming one.

Also re-examine the raking sweep against 1a: if its matrix has no divergent pair, the
void itself was built on a degenerate reading and must be recorded as such.

### 1d. Pre-commit the consequences, both directions

Write, before Phase 2 runs, what each outcome means:

- micronormal sweep DEGENERATE under 1a → the 1.0 carries no information; the three
  diffuse verdicts stand on the census with the flag `STANDING_WITH_A_MATERIAL_QUESTION_
  FLAGGED` cleared and replaced by the recorded reason; the amendment still stands as law
  for every future sweep.
- micronormal sweep VALID, and relief differs between a pair's two families, and that
  pair's two counted axes track above 0.80 → that pair FAILS. It gets no second argument
  and no substitute channel invented after the fact; the already-voided third channel is
  not re-opened for it, because relief is exactly the driver under which raking was shown
  to track. Recorded as FAIL.
- micronormal sweep VALID, but relief does not differ between a pair's two families →
  the sweep is irrelevant to that pair; it stands, and the record says why in one sentence
  that a stranger could check.

### 1e. Move the identity visibly

Hash the amended `PASS_LAW` / R5 text. Protocol identity moves from `087c7f64317910fb` to
the new hash. Record: old identity, new identity, the date, the reason in plain language,
the owner authorization (this brief), and a line stating that the pass bar 0.25, the R5
ceiling 0.80, the noise-floor margin 2.0 and `supporting_axes_never_count` are all
**unchanged** — the amendment adds a condition and moves no bar. Verify that claim by
diffing the two texts, not by asserting it.

Phase 1 exit: amendment written, hashed, committed, identity moved, supersession recorded
in place, and no measurement from Phase 2 onward yet consulted. Say so explicitly.

---

## PHASE 2 — ESTABLISH THE DRIVER SET, PER PAIR

For each of the three diffuse pairs, and for any other standing verdict whose counted
axes are read on the diffuse lobe or texture rigs:

1. Enumerate every parameter that differs in value between the pair's two families. Source
   it from the engine family definitions and `FAMILY_COMMON_OVERRIDES`, not from memory.
2. For each, classify: DECLARED_AND_REALIZED / DECLARED_BUT_NEVER_ARRIVES /
   BUILDER_CONSTANT_REALIZED_BUT_UNDECLARED / IDENTICAL_ACROSS_THE_PAIR.
   - `NEVER_ARRIVES` parameters cannot be drivers — they do not reach the render and
     cannot cause a correlated response. Exclude with the registry line as evidence.
   - **Builder constants that differ by family ARE drivers even though undeclared.** The
     under-declaration is a contract defect, not an exemption. Do not let the mirror
     defect hide a real driver. This is the specific trap in this phase.
3. For each surviving driver, state whether it is sweepable.
4. Report the driver set per pair as a table before sweeping anything.

State plainly whether `micronormal_amplitude` differs between the two families of each
diffuse pair. This single fact determines whether the alarming number is even on point,
and you do not know it yet — do not assume it does.

---

## PHASE 3 — MEASURE

For each sweepable driver identified in Phase 2 that is not already measured:

- Sweep on the rig that carries the counted axes, with the commissioned settings, seeds
  and controls already standing. Do not build a new rig.
- Retain and commit the **full pairwise matrix**, not the pairs of interest.
- Apply 1a first: is the matrix VALID or `SWEEP_DEGENERATE_UNDER_DRIVER`? Record the
  divergent pair that establishes validity, by name and value, or record its absence.
- Only then read the pairs of interest.

Re-run 1a against the already-measured micronormal sweep and the already-measured raking
sweep. If either full matrix was not retained, re-measure it rather than inferring
validity.

Every axis reading must still clear its own noise floor by the standing margin. A sweep
level whose axis response sits under the floor is not a level — it is noise, and it
corrupts the rank ordering. Check this before computing any rho, and report how many
levels survived.

---

## PHASE 4 — RE-ADJUDICATE

Under the amended, hashed law, re-rule every affected pair. For each, one paragraph: the
two counted axes, the census |rho|, the driver set, each driver's sweep validity, each
relevant sweep |rho|, and the verdict. Verdicts that degrade are committed. Verdicts that
improve are held as `AMENDMENT_INDUCED_IMPROVEMENT` per 1c.

Then answer the question the repair nodes are waiting on, in one line: **the number of
standing diffuse verdicts that `M6-CONTRACT-INTEGRITY-REPAIR` must not void is N**, with
N justified by the paragraphs above.

---

## PHASE 5 — VERIFY, ADVERSARIALLY

The suite may not verify itself. Before closing:

1. **Bar audit.** Diff the pre- and post-amendment law texts and prove mechanically that
   0.25, 0.80, 2.0 and `supporting_axes_never_count` are byte-identical. If any moved,
   the amendment was mis-executed — stop.
2. **Monotonicity check on the amendment.** Enumerate every currently-FAILing pair and
   confirm none becomes PASS under the amended law by way of condition (ii). Condition
   (ii) can only subtract. If one flips, the amendment as executed is not strictly
   additive and you have implemented something other than what Phase 1 declared.
3. **Negative control on 1a.** Construct or identify a driver sweep where two axes are
   known on physical grounds to be different instruments, and confirm the matrix shows
   divergence. If a known-good case reads all-1.0, 1a is not discriminating and must be
   reported as such.
4. **Silent-zero check.** Any axis reading exactly 0.0 across a sweep is
   `STIMULUS_NOT_REALIZED` until proven otherwise — the same defect already caught on
   `RAKING_SHADOW_FRACTION`. Sweep every axis for it explicitly.
5. **Self-approval check.** State which conclusions in this node rest on your own
   reasoning with no external artifact behind them, and list them separately.

---

## WHAT THIS NODE MAY NOT DO

- May not move any bar. Instruments get fixed; bars do not move.
- May not delete a superseded record. Supersede in place, with the prior text intact.
- May not invent a new channel, rig or axis to rescue a verdict. Any new instrument is a
  separately declared commissioning with its own floors, controls and realization gates.
- May not commit an improvement caused by the amendment without owner review.
- May not proceed into `M6-CONTRACT-INTEGRITY-REPAIR` (`b862941c303588f9`) or
  `M6-MARBLING-INSTRUMENT-REPAIR` (`04374a1057977dd1`) inside this node. Those start after
  N is known.

## BOUNDARY REPORT

Close with: the amendment text and both identities; the validity verdict on each sweep with
the divergent pair that carried it; the driver table per pair; the re-adjudication
paragraphs; N; the held improvements; the Phase 5 results including anything that failed;
and — separately from all of it — the single thing in this node you are least confident is
correct, stated as a question rather than a caveat.
