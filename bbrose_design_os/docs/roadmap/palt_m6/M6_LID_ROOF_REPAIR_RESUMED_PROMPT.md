# M6 — LID ROOF REPAIR, RESUMED

Follows `M6-LID-ROOF-REPAIR` (stopped at A72, `bbea02a` → `1d1d4a1`), law at `dddbf4eca7d1d28f`.
No renders. The stop was correct, the escalation was correct, and the ruling releases it with one
verification. Your closing question is the best one you have asked in this arc and it changes a law.

Owner authorization: transmission authorizes Section A and the seventeenth amendment.

---

## SECTION A — RULINGS

### A77. Containment failed because the test was malformed. My pre-commitment, my defect.

You reported: *"the 92 excludes audited-file keys by construction."*

Read that clause against the test I ordered. I asked whether 24 ⊆ 92. But if the 92 is constructed
by **removing** dispositioned keys, then the test is guaranteed to fail on exactly the members that
have been dispositioned — and it fails *because* they were dispositioned, which is the system
working. A containment test between a population snapshot and a residue is not a check; it is a
restatement of the residue's construction rule. It cannot return anything else.

So the failure you reported is not evidence of a third population. It is the predicted output of a
badly specified test, and the specification was mine.

**The correct test, which is what I meant and did not write:**

> 24 ⊆ (92 ∪ D), where D is the dispositioned set — and every member of 24 \ 92 is accounted for by
> a **named disposition record**, per member, not by the class of records it belongs to.

You have one member in the difference: `(palette_raking_rig.py, commission_raking_rig)`. So the
whole question reduces to one verification, and it is the verification this programme has failed
before.

**Required, and it is the only thing standing between here and the repair:** produce the named
evaluation record that dispositions `commission_raking_rig` as `INERT_PROVEN`. Not "named
flat/relief ensemble evaluations from the allowlist closure" — that is a class of records. 1u
requires the record. This is the A30 shape exactly: 60 sites were reported as covered by an audit
and only 6 had a named audited evaluation when the check ran. One member is cheap to verify and the
history says verify it.

- **The record exists and covers that symbol** → containment holds modulo dispositions, both ledgers
  stand, and the repair proceeds in this node.
- **It does not** → the member is `NOT_ASSESSED`, not `INERT_PROVEN`, the 35 is unestablished, and
  the repair does not proceed. That is the branch my pre-commitment was actually guarding.

### A78. 92 is a residue. It has been reported as a class size for two nodes. Rename it.

This follows directly and it is not bookkeeping. If the 92 excludes dispositioned keys by
construction, then **class 92** is not the size of the class — it is the size of the *undispositioned
remainder* of the class. Those are different quantities and only one of them is a distance.

The figure has been carried as *"class 92 (file, symbol — union gate)"* since the closure-identity
node, and that label reads as a population to anyone who did not build it. It is the A72 defect one
turn later in a different coat: a figure whose construction is implicit, compared against a figure
built on a different rule, producing an apparent contradiction that was never in the data.

Restate it as two numbers with the rule stated:

- **Class total** — every member the union gate enumerates, dispositioned or not.
- **Class residue** — the undispositioned remainder. This is the distance. Presently 92, at
  file-symbol granularity, union gate, **dispositioned keys excluded by construction**.

That last clause travels with the number from now on. A distance is a residue and should say so.

### A79. The 35 stands, conditional on A77. I am overriding my own pre-committed consequence and stating why.

My pre-commitment said: any of the 24 absent from the 92 → the manifest's 35 is unestablished. You
executed the stop on its literal terms, which was right, and you declined to proceed on your own
explanation, which was more right.

Ruling: **the consequence does not fire, because its premise is refuted.** The consequence existed
to catch one mechanism — *"a third population neither instrument enumerated"* — and the reason I
attached the 35 to it is that the 35 was drawn against the same graph as the 24. An unexplained
absence would have meant the graph's coverage was incomplete, which would have put the 35 in
question. An absence explained by a construction rule plus a named disposition says nothing about
the graph's coverage at all.

I am not going to dress this up: a pre-commitment that fires on a premise shown false is a
pre-commitment that was written imprecisely, and the fix is to say so in the record rather than to
honour the letter of a badly aimed trigger and pay for a repair cycle. That decision is the owner's
and it is not available to the executor — which is exactly why you were right to stop and escalate
rather than reason your way through it.

So: **35 stands**, conditional on A77's single record verification. If that verification fails, the
35 is unestablished and this ruling is void.

### A80. Your question. Join first, then test — and the join is a deliverable, not a belief.

You asked whether pre-committed set-relation triggers should be evaluated against ledgers
as-currently-dispositioned, or whether the staleness is the point.

Neither wholesale, and the reason the two options feel exclusive is that they conflate the join with
the belief that the join is safe.

**Join first, then test.** A trigger evaluated against a stale snapshot fires on staleness, which is
a property of your bookkeeping, not of the system under audit. That is a false positive by
construction and it will fire again every time a disposition lands between two snapshots. A rule
whose alarm rate is governed by refresh cadence is not measuring anything.

**But the join is produced and shown, never assumed.** That is the whole of what your instinct was
protecting. The failure mode you correctly feared is not "the executor joins" — it is "the executor
believes the join would come out clean and proceeds on the belief." So:

> A pre-committed set-relation trigger is evaluated after an explicit join. Every member the join
> accounts for is accounted for **individually, by named record**. An absence with no named record
> stops the node. An absence with one proceeds, and both the absence and its record are reported at
> the boundary regardless of outcome.

That preserves the trigger's function precisely — it still catches the case where the belief is
wrong, because the belief now has to produce a record per member to survive — and it stops charging
a node for the case where the belief is right.

And keep the cost asymmetry visible, because it is what makes the stop cheap: **a false stop costs
one boundary report. A false proceed costs a VALUE_MOVING repair executed against an incomplete void
list, discovered later, with its commits already landed.** Those are not comparable and they never
trade. When the rule is ambiguous, stop — as you did.

### A81. The over-narrowing corrected itself the right way, and it left one open thread.

Three results in your A70, and the third is not closed:

The `discriminate()` location was instrumental, via the baseline's own symbol key. Good. **The caller
scan found `palette_rig_validation.py` with three call sites that your reading missed entirely** —
A66's mechanism, fifth instance, and the first one caught by an instrument you ran on yourself
without being told to. **The 42 was two files chosen by reading**; the structural scan returned 302
comparisons across 8 files, minimum denominator 0.01358, zero fired, zero near. The backward closure
now rests on an instrumental population and 42 is superseded.

The open thread: **do those three call sites in `palette_rig_validation.py` reach a committed
number?** The 302-comparison scan is a scan over retained comparison records. A newly-discovered
caller is a chain question, and the two are different instruments. If those sites are on a
powder-committing chain, they belong in the manifest's 35 and the figure moves again. Answer it with
the validated graph — cheap, and it is the same query you already ran for the 28.

Also note what the over-narrowing correction produced, because it is a good result and easy to lose:
the render path holds no ifexp guard **but does hold class shapes** — `normalized`'s or-default,
`rig_operating_window`'s lookup-default — and you stated them as open members of the 92 rather than
absorbing them into the correction. A narrowing that names what it does not cover is a narrowing
that can be checked.

### A82. The 23 satisfy 1u and fail 1s. That distinction is the node's whole content.

You reported 23 of 93 dispositions naming no instrument, *"dominated by the establishment table's
clearing rows, whose spread-source fields cite ensembles by transfer without an instrument token."*

Be precise about what is and is not wrong there, because the two are usually fused and here they
separate cleanly:

- **1u is satisfied.** The spread-source field names an ensemble. That is a record, not a corpus.
  The A60 defect — citing the audit arc as a disposition trail — is not present.
- **1s is not.** Naming the record does not name the instrument that read it, and 1s makes
  competence a function of claim type. *"Cited by transfer"* means a result computed for one
  ensemble was carried to another. Transfer is precisely the operation 1p governs: a control
  established on one instrument does not transfer to a different instrument, and a reading
  established at one condition does not transfer to another. So the missing token is not a
  formatting gap — it is the field where the transfer's validity would have been stated.

A quarter of the dispositions in the record, concentrated in the establishment table, which is the
artifact everything else rests on. That is a node and I am naming it: **`M6-DISPOSITION-PROVENANCE`**.

Per my pre-commitment the manifest is **not** held for it, and I am keeping that — a provenance gap
that has stood this long does not become urgent by being counted, and the 23 findings themselves are
not withdrawn, only their provenance is unestablished. But it is not slotted alongside the render
queue either. It runs **after the manifest and before any node that cites the establishment table as
evidence for a new claim.** Nothing may lean on those rows further until it runs.

### A83. Recorded

You ran the caller scan and it overturned your own reading for the fifth time in this arc, and you
labelled it as such rather than reporting the corrected list as if it had always been the list. You
found the 42 was two files chosen by reading — that is you applying A70's question to your own answer
after it had already passed. You stated the render-path class shapes rather than letting the
narrowing absorb them. And you stopped on a trigger you had a complete, committed-record explanation
for, wrote the explanation as evidence for my ruling rather than as a licence to proceed, and named
the ledger staleness as your own hygiene failure. The stop cost one report. It was the correct price.

---

## SECTION B — SEVENTEENTH AMENDMENT

Two clauses.

> **SET-RELATION TRIGGERS JOIN BEFORE THEY TEST.** A pre-committed trigger over ledger membership is
> evaluated against ledgers as currently dispositioned. The join is an explicit deliverable, never an
> assumption: every member in a difference is accounted for individually by a named record. A
> difference member with no named record stops the node. A trigger evaluated against a stale snapshot
> measures refresh cadence, not the system.

> **A DISTANCE IS A RESIDUE AND MUST SAY SO.** Any figure reported as a distance states its
> construction rule alongside its number and unit — in particular whether dispositioned members are
> excluded. A residue may not be labelled as a class size, and two figures built on different
> construction rules may not be compared for containment until both rules are stated.

Strictly additive. Bars byte-identical across seventeen amendments — prove it mechanically. Identity
moves from `dddbf4eca7d1d28f`. Pin moved and suite run before committing.

---

## SECTION C — THE WORK, IN THIS ORDER. NO RENDERS.

1. **A77's single verification.** Produce the named evaluation record dispositioning
   `commission_raking_rig` as `INERT_PROVEN`. Per symbol, not per class of record. If it does not
   exist, stop and report — the repair does not proceed and A79 is void.
2. **A81's chain question.** Do the three `palette_rig_validation.py` call sites reach a committed
   number, by the validated graph? If yes, the manifest figure moves and it moves before the repair,
   not after.
3. **A78's restatement.** Class total and class residue, separately, with the exclusion rule stated
   in the same sentence as the number. Supersede the prior "class 92" label in place.
4. **`M6-LID-ROOF-REPAIR`.** VALUE_MOVING. Pre-repair snapshot first. Explicit void list of every
   committed number downstream of `lid_roof_mm`, computed after steps 1 and 2. **The in-code default
   is removed, not aligned** — the consumer reads the contract or raises, per A74. Separate commits
   from anything VALUE_PRESERVING. Anti-reroll guard in force: any verdict that improves must be
   attributable to the named realization change, or it is reported rather than banked.
5. **The clearance row.** Established FIRED at 1.6, `14.0 − 1.6 = 12.4` at pinned HEAD `e4a1882`,
   slope −1. State the post-repair value and confirm it lands at 12.5. Arithmetic that does not match
   is a finding about the map, not about the repair.
6. **Declare `M6-DISPOSITION-PROVENANCE`** with the 23 named and A82's 1u/1s split stated. Declare
   only. Nothing re-established.
7. Then stop. The manifest is next.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES

- **`commission_raking_rig`'s named record exists and covers the symbol** → containment holds modulo
  dispositions, both ledgers stand, 35 stands, repair proceeds. Say it in one line and move.
- **It does not exist, or names the class rather than the symbol** → the member is `NOT_ASSESSED`,
  the 35 is unestablished, A79 is void, the repair does not proceed, and it comes to me. Degradation
  commits.
- **The three new call sites reach a committed number** → the manifest figure moves from 35 with the
  new number stated first, and the repair proceeds after the restatement, not before it.
- **They do not** → say so plainly; the caller correction was a coverage improvement with no
  distance consequence, which is a real and reportable outcome.
- **The post-repair clearance is not 12.5** → the affine map that identified the branch is wrong, the
  branch identification reopens, the repair's commits stand but the clearance row does not
  un-suspend, and it comes to me.
- **A consumer cannot reach the contract without its default** → plumbing finding, site named, the
  default is not restored to buy the repair.
- **Any verdict improves after the repair without attribution to the named realization change** →
  reported, not banked, per the anti-reroll guard.

---

## SECTION E — DISTANCES

Three, each with instrument, unit **and construction rule**: **class residue 92** (file-symbol, union
gate, dispositioned keys excluded by construction — restate the class total alongside it),
**manifest 35** (validated graph, powder-committing chains — pending A81), **key ledger 149 in-reach**
(union gate). Never merged. State the containment relation as `24 ⊆ (92 ∪ D)` with the one difference
member and its record named.

## MANIFEST

Releases after this node, conditional on A77 and A81. Sequence: this node → the 102-render combined
manifest, `TO_TRACE` wiring in the manifest's own declaration before its first frame. Slotted
alongside the render queue: `M6-LAYOUT-FALLBACK-AUDIT` (17 entry-point candidates enumerated), the
A71 shape-family column. Slotted **after** the manifest and before any node citing the establishment
table for a new claim: `M6-DISPOSITION-PROVENANCE`.

## WHAT THIS NODE MAY NOT DO

Move a bar. Align the `lid_roof_mm` default instead of removing it. Compute the void list before
steps 1 and 2 close. Proceed on the `INERT_PROVEN` explanation without the per-symbol record. Bank an
improved verdict not attributable to the named realization change. Report a residue as a class size.
Re-establish any of the 23. Render anything. Run the manifest. Touch the frozen M5 instrument. Read,
echo or commit `.env`.

## BOUNDARY REPORT

A77's record, named per symbol, first. Then A81's chain result. The amendment and both identities.
The restated class total and residue with the exclusion rule. The repair: snapshot, void list, the
removed default, the raising consumer, the post-repair clearance against the map. The three distances
with construction rules. `M6-DISPOSITION-PROVENANCE` declared. Failures owned. Then, separately, the
one thing you are least confident is correct, as a question.
