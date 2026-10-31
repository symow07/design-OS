# M6 — REACHABILITY INSTRUMENT

Follows `M6-ALLOWLIST-COVERAGE-CLOSURE` (`cd61faa` → `4a48a14`), law at `c0749e29521a2728`.
No renders. It replaces an asserted reachability claim with a measured one, audits the 27,
and attaches the firing trace to the manifest instead of to a node of its own.

Owner authorization: transmission authorizes Section A and the tenth amendment.

---

## SECTION A — RULINGS

### A34. Yes, and it voids all 43 rather than the four you noticed

Module-set membership is not reachability. It is an assertion about reachability, written by
hand, and 1s condition 1 requires a **declared static instrument of record** — a list is a
declaration but it is not an instrument. Conditions 2 and 5 you satisfied properly; condition
3 you answered by assertion. You have already named the precedent yourself: A18 exists because
a static instrument's *scope definition* was where it failed.

The part to correct is the scope of your own doubt. You flagged `palette_layout_kernel`
because you happened to notice it holds four of the 43. But the instrument was the same
instrument for all 43, and an instrument that is not competent does not become competent for
the entries where nobody looked. That is 1q's scope check turned on this node: *what is the
class, and does the doubt cover all of it, or only where it was found?*

**All 43 revert to `NOT_ASSESSED`.** Degradation, so it commits immediately. Re-discharge only
what the graph clears.

Note what does and does not follow in the interim. `NOT_ASSESSED` propagates only to
*enumerated* downstream numbers, and for these 43 the enumeration is exactly what the graph
has not yet produced — so nothing suspends today. That is not a loophole and you should not
report it as reassurance: nothing suspends because **the queue is stopped**, not because the
status is benign. If any measurement node runs while those 43 sit un-enumerated, that is the
violation, and Section E holds precisely to prevent it.

### A35. The asymmetry that makes the import graph the right instrument, and its limit

Import-graph reachability is coarse: importing a module does not mean calling the function
that holds the site. Coarse is the safe direction here, and it gives the instrument a shape
this programme already knows:

> **Import-graph reachability is sound for refutation and unsound for confirmation.** A site
> in a module not import-reachable from any measurement entry point cannot be called by a
> measurement computation, and the discharge is established. A site that *is* import-reachable
> has been shown nothing — not that it fired, not that any committed number is downstream. It
> returns `NOT_ASSESSED`, and only a finer declared instrument can move it.

That is 1p's sensitivity/specificity asymmetry, applied to static analysis instead of to
measurement instruments. The same rule, in the same programme, one level down.

A call graph is the finer instrument and it is the *less* trustworthy one, because Python call
graphs are unsound wherever dispatch is dynamic. If you reach for one, enumerate its
unsoundness sources first and state which apply here: dynamic import (`importlib`, `__import__`),
`getattr`-based dispatch, decorator and registry indirection, callbacks passed as values,
`eval`/`exec`, and entry-point or plugin loading. Any site whose reachability turns on one of
those is not decided by the call graph and stays `NOT_ASSESSED`.

Check for dynamic import explicitly before trusting the import graph at all, since a single
`importlib` call in the measurement set defeats the whole instrument silently — which would
make the reachability instrument itself a member of the class it is auditing.

### A36. A30's gap was created by my brief, and the rule that prevents it is general

Own this on my side of the record. My Section C in the firing-audit brief asked for two things
— *"report by consumer, not by site"* and *"disposition all 62 allowlist entries"* — as
independent deliverables. They were independently satisfiable, you satisfied them
independently, and the join between them was never required by anything I wrote. 383
computations were audited thoroughly and 56 of 62 sites were never touched by the audit that
was then cited as their evidence. That is my defect, and it should sit in the record next to
yours.

The general rule it yields, which is what I actually want out of it:

> **A disposition citing evidence must name the record, not the corpus.** "The audit proves
> it" is not a disposition. "Audited computation N evaluated this site at denominator D" is.
> Where a set of dispositions is discharged by a set of records, the join between them is
> itself a required deliverable, not an inference.

Had that been law, A30 would have been impossible to write rather than merely wrong.

### A37. The 27 are probably not a new class. They may be the mechanism behind an old one.

`dict.get(k, default)` in builder or measurement code is precisely how a declared parameter
becomes an unrealized one: the key is absent or misspelled, the default silently wins, and the
declared value never reaches the render. That is `DECLARED_BUT_UNREALIZED`'s mechanism, and it
is invisible to a census that asks only whether a parameter name is referenced somewhere.

So before treating the 27 as a new finding, **cross-reference them against the 49 dead
parameters and the 25 under-declared builder constants.** Three outcomes, all of them worth
having:

- **They overlap substantially** → the 27 are the mechanism behind a class already counted,
  the defect register gains a cause where it had only a count, and the dead-parameter census
  gains an explanation it has never had.
- **They do not overlap** → there are 27 silent substitution points in measurement code that
  no census has ever looked at, and they get Section C's firing method.
- **Partial** → report both parts separately and do not average them.

Note the difference in firing character, because it changes what the audit asks. A division
guard fires on a rare numeric condition and is detectable from retained denominators. A
lookup-default may fire on **every single call by design**, because the key is legitimately
optional. So the question is not "did it ever fire" but "**where firing occurred, was the
default a declared value or a silent substitution for a value that should have been present?**"
Firing constantly and by design is not a defect. Firing constantly while a declared parameter
sits unread three files away is the defect this programme was built to catch.

### A38. The firing-trace instrument attaches to the manifest, at zero marginal render cost

You deferred it as a repair-node item because tracing firing requires running the code, and
running measurement code means rendering. But the manifest is going to render 102 frames
regardless. Instrument the sites first and the trace is a **free byproduct of work already
scheduled**, rather than a node that has to buy its own renders.

Conditions, all before the first frame:

1. **Declared and committed before the manifest starts.** Added mid-queue it is an instrument
   changed during a measurement, which is the shape 1n governs.
2. **Records per firing:** site, the computation that invoked it, the input that triggered the
   fallback (denominator or missing key), and the value substituted.
3. **Failure to log is a suite failure, not a silent skip.** A trace instrument that quietly
   fails to record produces an empty trace, an empty trace reads as "nothing fired," and that
   is a plausible in-range result from malformed input — the instrument would be a member of
   the very class it audits. Guard it accordingly.
4. **Positive control, before the manifest.** Deliberately fire a fallback in a test and
   confirm the trace records it. A trace instrument that has never been shown capable of
   recording a firing is not validated at the condition of its reading — 1p, applied to it.
5. **Prospective only.** It discharges nothing already committed. Every number the manifest
   produces gains firing evidence; no number produced before it does.

### A39. Two instruments, and I cannot tell which is which

One of your scans matched a comment line describing the removed 1g fallback. An AST instrument
cannot match a comment, so at least one of the two scans in play is textual. State plainly
which is which: the exit-path analysis in Section C, and the guard test that scans for fallback
shapes and now fails the suite on new occurrences.

If the **guard test** is textual, that is a scope defect of A18's exact family and it matters
in the direction that hides: a text scan misses semantically identical code written
differently — a different variable name, a line break, a ternary spelled as an `if`. The 27 is
then a floor and not a count. Convert it to AST and re-report the number; if the number does
not move, that is a real result and it hardens the 27.

Separately, reconcile two figures I cannot join from the report: the firing audit covered
**383 computations**, the conditioning analysis covered **180 denominators**. Say what the
other 203 are — a different denominator form, a subset scoped deliberately, or computations
that share denominators — and confirm the conditioning band was applied to everything it should
have been.

### A40. Recorded, on the other side of the ledger

A33 landed a genuine convergence: two independent instruments, commissioned for unrelated
reasons, pointing at the same defect. The conditioning band was declared before computing at
5× the realization floor, and it found the marbling axis's operands sitting at 2.5× — which
corroborates the placement diagnosis from a direction that had nothing to do with placement.
Corroboration from an instrument that could have disagreed is worth more than the finding it
confirms.

And A30 invalidated 90% of your own prior node's central claim, reported without softening,
with the number stated first. That is the fourth time in this arc the executor has surfaced the
defect in its own work before anyone asked. Recorded.

---

## SECTION B — TENTH AMENDMENT

Hash A35's static-reachability asymmetry and A36's evidence-citation rule. Check the label is
free and record the collision if not, as you did with `1n`.

Strictly additive. Bars byte-identical across ten amendments. Identity moved from
`c0749e29521a2728`. Pin moved and suite run before committing.

---

## SECTION C — THE WORK. NO RENDERS.

1. Revert all 43 to `NOT_ASSESSED` and commit that first, before running anything that could
   restore them. The reversion is the degradation; the restoration is what has to be earned.
2. Check the measurement set for dynamic import before trusting the graph.
3. Build the import-graph instrument from declared measurement entry points. Re-discharge only
   what it clears, as `INERT_BY_UNREACHABILITY`. Everything else stays `NOT_ASSESSED` with its
   downstream enumerated.
4. A37's cross-reference, then the firing character audit of the 27.
5. A39's instrument statement, the AST conversion if the guard test is textual, and the
   383/180 reconciliation.
6. Declare the A38 trace instrument with its positive control. Do not run the manifest.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES

- **The graph clears all 43** → they return to `INERT_BY_UNREACHABILITY` on measured rather
  than asserted evidence, and the allowlist closes on an instrument of record.
- **The graph clears fewer than 43** → the remainder stay `NOT_ASSESSED` with enumerated
  downstream. Any that reach a floor or seed-only computation re-plan the manifest.
  Degradation: commits immediately.
- **Dynamic import found in the measurement set** → the import graph is not a competent
  instrument here, all 43 stay `NOT_ASSESSED`, and you stop and escalate rather than choosing
  a substitute instrument yourself.
- **The 27 overlap the dead-parameter census** → recorded as mechanism, not as new class, and
  the census gains a cause.
- **The 27 fire as silent substitution for declared values** → that is `DECLARED_BUT_UNREALIZED`
  recurring after a repair that claimed to close it, and it is recorded as a recurrence with
  that severity, not as a new count.
- **The AST conversion moves the 27** → the guard test's prior counts are all floors and every
  number resting on them is restated.

---

## SECTION E — MANIFEST GATING

The 102-render manifest releases when: all 43 are dispositioned on the graph, the 27 are
dispositioned or shown not to touch a committed number, the 10 `NOT_ASSESSED` measurement sites
are confirmed to reach no floor or eligibility computation the manifest depends on, and the
A38 trace instrument is declared with its positive control passing.

On the 10: your reasoning that nine reach only frozen-M5 or non-committed numbers, and that the
tenth reaches a record already `NOT_ESTABLISHED_PENDING_SPREAD`, is an argument that they do not
*worsen* anything. It is not yet an argument that the manifest is clear of them. The question to
answer is narrow — **does the glitter event record feed any floor, eligibility or clearing
computation the manifest will consume?** If it feeds only a verdict already suspended, the
manifest proceeds. If it feeds a floor, it does not.

---

## WHAT THIS NODE MAY NOT DO

Move a bar. Repair a fallback site. Restore a discharge the graph did not clear. Substitute a
different instrument if the import graph proves incompetent — escalate instead. Render anything.
Run the manifest. Touch the frozen M5 instrument. Read, echo or commit `.env`.

## BOUNDARY REPORT

The amendment and both identities, pin moved and suite run before the commit. The 43 reverted,
then the graph's result per entry. The dynamic-import check. The 27 cross-referenced against 49
and 25, with the firing-character finding. Which instrument is AST and which is textual, the
converted count, and the 383/180 reconciliation. The trace instrument declared with its positive
control. The glitter-record answer. Whether the manifest releases. Failures owned. Then,
separately, the one thing you are least confident is correct, as a question.
