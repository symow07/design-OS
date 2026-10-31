# M6 — COMBINED MANIFEST

Follows `M6-LID-ROOF-REPAIR, RESUMED` (`a674e8e`), law at `7ab59fc6860bd75c`.
**The first renders in nine nodes.** 102 frames, and the ordering constraint in A89 is the one thing
in this brief that cannot be recovered from if it is got wrong.

Owner authorization: transmission authorizes Section A and the eighteenth amendment.

---

## SECTION A — RULINGS

### A84. Neither option. Both of them assume one row, and there are two.

Your question offers: banked under step 4's clause, or reverted to suspended pending my
confirmation. The reason neither feels right is that both treat the clearance row as a single record
changing status. It is not.

**A repair does not un-suspend a row. It supersedes it.**

The old row recorded a number computed on 1.6. That number *was* committed, the substitution *did*
fire, and no repair reaches backwards to make that untrue. It stays suspended, permanently, as the
record of what was committed under the defect. Nothing lifts it, and nothing should — the arc spent
four nodes establishing that firing and the record of it is the arc's product.

The repaired number is a **new row**: a different computation, on a different input, at a different
HEAD. It does not inherit the old row's status in either direction. It is not un-suspended, because
it was never suspended. It is not banked as an improvement, because it is not the same quantity
improving.

This also answers A44's apparent conflict cleanly. I wrote there that *"un-suspending a row labelled
FIRED is an improvement requiring my ruling."* That governs the case where the firing turns out not
to have happened — the finding was wrong and the row is being restored. Here the finding was right,
the defect was real, and nothing about the old row is being disturbed. Supersession in place is what
this programme does with superseded records everywhere else; it applies here without exception.

So: the old row stands suspended with its 12.4 and its FIRED substitution. The new row carries 12.5.
Both are in the record, adjacent, and the reader can see the repair by comparing them. That is
strictly more informative than either of your options.

### A85. A restriction clause is not an authorization. This is the ruling that matters beyond today.

Your reading of step 4 was reasonable and it is wrong, and the reason it is wrong generalises.

I wrote: *"any verdict that improves must be attributable to the named realization change, or it is
reported rather than banked."* Read the grammar. That sentence states a **condition under which
banking is forbidden**. It does not state a condition under which banking is permitted. A filter is
not a licence.

Follow the alternative reading through, because it is the argument against it: if an anti-reroll
guard authorizes banking whenever attribution succeeds, then every anti-reroll guard in the
programme becomes a standing self-authorization for any improvement the executor can attribute — and
attribution is performed by the executor. That inverts 1c completely. 1c exists precisely because the
party who produced an improvement is not the party who should judge whether it is real.

The general form, and it is going in the law: **a clause that constrains an action never authorizes
it.** Where a node needs authority to bank an improvement, the authority is stated affirmatively, by
me, in the transmission. Absent that, an improvement is held regardless of how well it is attributed.

You committed under a misreading of my text, and my text was ambiguous enough to support it. The
commit stands — A84 makes it moot, because the new row was never an improvement to bank. But record
the misreading and the clause, because the next one may not be moot.

### A86. `REPAIRED_RECOMPUTED_ESTABLISHED` asserts more than you demonstrated.

Three words, three claims, and only two were shown. Repaired: yes. Recomputed: yes, and the 12.5
matches the affine map exactly, which is a real confirmation. **Established: not demonstrated —
inherited.**

The new row is a new establishment and it starts from nothing. Establishment is not a property a row
keeps across a repair; it is a claim about a computation, and this is a different computation.

The good news is that this row's establishment is cheap and probably already holds, because the
quantity is deterministic arithmetic on contract-declared inputs. So state it rather than assume it:
the inputs are contract-declared and singly-stated, the arithmetic is deterministic, the affine map
is independently verified, and the result is reproducible from the record. That is an establishment
argument, it takes four lines, and it makes the label honest.

If any input to the clearance is *not* contract-declared, that is a finding and the row is
`RECOMPUTED_PENDING_ESTABLISHMENT` until it is.

### A87. Attribution by name is weaker than attribution by slope. You have the slope; use it.

The anti-reroll guard's entire force is attribution, and you attributed *"by name to the lid_roof
realization change."* A name is an assertion. The chain gives you something better and you already
computed half of it.

State the composed chain with the slope at each hop: `lid_roof_mm` −0.1 → `lid_roof_underside_z`
+0.1 (slope −1, confirmed by `14.0 − 1.5 = 12.5`) → worst-case clearance +0.1 (slope ?). Confirm the
composed slope predicts the observed 5.35 → 5.45 exactly, with no residual.

Two reasons this is not pedantry. A residual would mean something *other* than the repair moved,
which is exactly what the anti-reroll guard exists to catch and which a name-attribution cannot
detect. And a sign that composes to the right magnitude by two cancelling errors is a classic
arithmetic failure — the same 0.1 arriving with slope −1 in one quantity and +1 in another looks
correct at a glance and is checkable in one line. Where the map can attribute, the map attributes.

### A88. The line-keyed allowlists are a live finding, not a slip you fixed.

You reported, as an owned slip: *"the repair's added lines tripped the line-keyed legacy allowlists —
the exact fragility your symbol-keyed baseline rule named, demonstrated live and fixed."*

The demonstration is the finding. A53 required the *new* baseline be keyed on file, symbol and shape
specifically so that *"the first reformat trips every entry and the gate gets disabled by whoever is
unlucky enough to be on shift."* That reasoning applied to a hypothetical. It has now happened, on a
four-line repair, and it will happen on every subsequent edit to any file a legacy allowlist covers.

Fixing the entries this repair tripped is not fixing the class. **Enumerate every allowlist in the
record still keyed on line numbers, and declare `M6-ALLOWLIST-REKEY` to move them to the
file/symbol/shape convention.** Count in this node; re-key in that one. It is a documentation and
mechanical-transform node with no render cost, so it slots alongside the render queue on A68's
reasoning, next to the layout audit.

And note the shape for the register: a fragility argued in the abstract and accepted on the argument
was not acted on for the existing population, only for the new one. That is the same partial
adoption A42 found in the contract repair's scope — a rule applied where it was discovered rather
than across its class, which is 2d.

### A89. The manifest. TO_TRACE lands before the first frame, and this is the irreversible one.

Everything else in this brief can be corrected in a later node. This cannot, because renders are the
scarce resource and a frame rendered without the trace cannot be retroactively traced.

The reasoning chain, stated once so it is not re-derived under pressure:

The 35 manifest-gate sites are in-reach and un-dispositioned. Per A62 the trace closes them
**prospectively** — for numbers the manifest produces, not for numbers already committed. So the
trace is not an observability nicety attached to the render run; **it is the disposition instrument
for the 35, and the manifest's numbers are its readings.** A frame rendered before the wiring
produces a number that is backward-open on 35 sites, cannot be closed by the trace afterwards, and
must be re-rendered — spending the scarce resource twice, which is the argument that ordered this
entire release sequence.

So, before frame one:

1. **`TO_TRACE` wiring lands in the manifest's own declaration.** Not in a prior node, not after the
   first frame, not as a follow-up commit.
2. **The trace instrument runs against the seeded corpus** — 2a, reflexive validation. It is an
   instrument commissioned to detect this class and therefore a candidate member of it. Two of the
   four instruments built in this arc fired live. Do not let this one be the third by skipping the
   check that exists for it.
3. **Positive control**, per A38's conditions: feed it a known firing, confirm it records; feed it an
   empty run, confirm the writer raises rather than producing a clean empty trace that reads as
   "nothing fired."
4. **PASS_LAW declared before measurement**, in writing, in the declaration: two required independent
   axes, 0.25 relative effect bar, supporting axes never count, R5 ceiling 0.80, noise-floor
   separation margin 2.0. Declared, then measured. Not restated afterwards to match.
5. **Negative controls declared with the ensembles**, not assembled after the readings.

Only then does the render queue open.

Budget discipline: 102 frames is the declared spend and it is not open-ended. If the queue must
grow, it comes to me with the reason before the extra frames run, not in the boundary report after.

### A90. Recorded

The A77 verification came back with three per-site records including a `NOT_IN_CLASS` for a comment
line — you did not quietly drop the third member to make the answer tidier. A81 came back "no
distance consequence" and you stated it plainly rather than finding a way to make a five-node
correction look like it moved something. You caught the plumbing landing before the contract bound
on the immediate run, which is the run existing to catch exactly that. And you escalated a status
change you had already committed, against your own interest, on a reading of my text that was
defensible — that is the behaviour that makes the ambiguity in my clause recoverable instead of
permanent.

---

## SECTION B — EIGHTEENTH AMENDMENT

Two clauses.

> **A RESTRICTION IS NOT AN AUTHORIZATION.** A clause stating conditions under which an action is
> forbidden does not thereby permit the action when those conditions are absent. Authority to bank an
> improvement, lift a suspension, or move a status is stated affirmatively by the owner in the
> transmission. Absent an affirmative grant, 1c governs and the improvement is held.

> **REPAIR SUPERSEDES, IT DOES NOT RESTORE.** A record suspended because the computation it holds was
> produced under a defect is not un-suspended by repairing the defect. It stands as the record of what
> was committed. The repaired quantity is a new record, establishing on its own terms, inheriting no
> status in either direction, and placed adjacent to the superseded one so the repair is visible by
> comparison.

Strictly additive. Bars byte-identical across eighteen amendments — prove it mechanically. Identity
moves from `7ab59fc6860bd75c`. Pin moved and suite run before committing.

---

## SECTION C — THE WORK, IN THIS ORDER

**Steps 1–4 carry no renders. The queue does not open until 4 closes.**

1. **A84's split.** Old clearance row stands suspended with 12.4 and its FIRED substitution,
   permanently. New row created adjacent, carrying 12.5. Neither inherits the other's status.
2. **A86's establishment argument** for the new row — inputs contract-declared and singly stated,
   deterministic arithmetic, affine map independently verified, reproducible from the record. If any
   input is not contract-declared, the row is `RECOMPUTED_PENDING_ESTABLISHMENT` and that is the
   finding.
3. **A87's composed slope.** Full chain, slope per hop, composed slope predicting 5.35 → 5.45 with no
   residual. A residual stops the node.
4. **A88's count** — every allowlist still keyed on line numbers, enumerated. Declare
   `M6-ALLOWLIST-REKEY`. Count only; re-key nothing here.
5. **The manifest declaration**, with A89's five preconditions in it and each demonstrated:
   `TO_TRACE` wired, trace run against the corpus, positive control and raising-writer control both
   passed, PASS_LAW declared in writing, negative controls declared with the ensembles.
6. **The 102-frame queue runs.** `M6-DECLARED-ENSEMBLE-SPREADS`, `M6-CENSUS-REPLICATE`, and the
   control-coverage gaps, as declared.
7. **The trace reading**, per site, for the 35. Forward closure only — say so explicitly, and name
   which of the 35 the trace actually exercised versus which it did not reach, because a site the
   queue never executed is not closed by a trace that ran.
8. Then stop. Report before any verdict is acted on.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES

- **A87's composed slope leaves a residual** → something other than the repair moved, the repair's
  attribution fails, the new row does not establish, and it comes to me before the queue opens.
- **An input to the clearance is not contract-declared** → `RECOMPUTED_PENDING_ESTABLISHMENT`, named,
  and it joins the contract-reconciliation class rather than being repaired here.
- **The trace fails its corpus run** → it is the third instrument in this arc to be a member of the
  class it audits, its readings carry nothing, and **no frame renders** until it passes. Degradation
  commits and the manifest holds.
- **The raising-writer control does not raise on an empty run** → same consequence. An empty trace
  that reads clean is the original A38 hazard and it does not get to reach production.
- **The queue does not exercise all 35 sites** → the unexercised sites remain `NOT_ASSESSED`, are
  named individually, and the manifest's closure claim is stated with its actual coverage rather
  than as "the 35."
- **Any verdict improves relative to the pre-repair record** → held, not banked, per the eighteenth
  amendment, and placed with me under 1c. This is the affirmative statement A85 requires: **you do
  not have authority to bank an improvement in this node.**
- **The queue needs more than 102 frames** → it comes to me with the reason before the frames run.
- **PASS_LAW is not met on the powder families** → that is a legitimate result, reported as FAIL with
  the axes and effect sizes stated. The bar does not move. It has not moved in eighteen amendments
  and it does not move for a verdict.

---

## SECTION E — DISTANCES

Report four now. **Class residue 92** (file-symbol, union gate, dispositioned excluded; total 274
alongside). **Manifest 35** (validated graph, powder-committing chains) — and after the trace, split
it into *closed forward by trace* and *not reached by the queue*, never merged. **Key ledger 149
in-reach** (union gate). **Line-keyed allowlist entries** (A88's count, new).

## MANIFEST

This node is the manifest. After it: `M6-DISPOSITION-PROVENANCE` before any node cites the
establishment table for a new claim. Alongside the render queue, competing for nothing:
`M6-LAYOUT-FALLBACK-AUDIT` (17 entry-point candidates enumerated), the A71 shape-family column,
`M6-ALLOWLIST-REKEY`. Then `M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION`, `M6-FLOOR-STATISTIC-REPLICATE`,
`M6-FROZEN-INSTRUMENT-DEFECT-REGISTER`, and the M6 exit gate against the full canonical suite.

## WHAT THIS NODE MAY NOT DO

Move a bar. Un-suspend the old clearance row. Bank any improvement — no affirmative grant is given.
Render a frame before `TO_TRACE` is wired and both trace controls have passed. Exceed 102 frames
without my ruling. Report the 35 as closed where the queue did not exercise them. Re-key any
allowlist. Restate PASS_LAW after a reading. Touch the frozen M5 instrument. Read, echo or commit
`.env`.

## BOUNDARY REPORT

A84's two rows, adjacent, first. A86's establishment argument. A87's composed slope with its
residual stated as zero or not at all. A88's count and the declared re-key node. The amendment and
both identities. The five manifest preconditions, each demonstrated, with the trace's corpus result
and both controls. The 102 frames and what they cost. The trace reading per site, with the 35 split
into closed-forward and not-reached. The verdict against PASS_LAW as declared before measurement.
The four distances. Failures owned. Then, separately, the one thing you are least confident is
correct, as a question.
