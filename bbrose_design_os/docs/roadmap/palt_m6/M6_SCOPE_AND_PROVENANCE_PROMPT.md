# M6 — SCOPE AND PROVENANCE

Follows `M6-REACHABILITY-INSTRUMENT` (`66b2121` → `15bf452`), law at `78eed7f5efe6fba7`.
No renders. Two of your findings are larger than the report treats them, and the escalation
resolves narrowly.

Owner authorization: transmission authorizes Section A and the eleventh amendment.

---

## SECTION A — RULINGS

### A41. The 27 → 28 result does not stop at 28. It puts the 62 in question.

You proved textual counts are floors by finding one site hiding under a line break. That is a
property of the instrument, not of that scan, and it applies to **every count that instrument
ever produced.**

So: which scan produced the original 62? If the A22 census was textual — and the guard test
descended from it was — then 62 is a lower bound and *"62 scanned shapes, 61 confirmed class
members"* are both floors. That is materially worse than a mis-disposition. A mis-dispositioned
site is a wrong row in a table you have; an un-enumerated site is a row that was never written,
and the entire allowlist has been reasoning about a population it never established the size
of. Every disposition in the last three nodes rests on the enumeration being complete, and
completeness was never claimed by an instrument competent to claim it.

Re-run the original census under AST and restate the number. Then apply the same question to
every other count in the record that came from a text scan and say which figures move. If
nothing moves, that is a real result and it hardens all of them at once.

### A42. The contract repair's scope was never checked against its class. That is the finding.

You recorded the `lid_roof_mm` substitution as `DECLARED_BUT_UNREALIZED` recurring "in the case
contract outside the powder census the repair swept." Read that sentence again as a statement
about scope rather than about a parameter.

`M6-CONTRACT-INTEGRITY-REPAIR` declared a class closed. It swept the powder census. Nothing
established that the powder census *is* the class, and 1q makes that check mandatory when
declaring any structural guard: **what is the class, and does the guard cover all of it, or
only where it was found?** The contract repair is a structural guard missing its own scope
check, and the 0.1mm is how we found out.

Required, and it is the substance of this node:

1. **Enumerate every declared contract in the system** — case, powder, colour, geometry,
   whatever exists — not every parameter, every contract.
2. Per contract: was it swept by the contract-integrity repair, and by what instrument.
3. For every unswept contract, reconcile declared values against the values consumers actually
   receive, by evaluating the consumer rather than by reading it. That is what caught
   `lid_roof_mm` and it is the method that works.
4. Report the count of substitutions found per contract. If unswept contracts return zero, say
   so — that hardens the repair's claim by showing its scope was accidentally correct, which is
   worth knowing and is not the same as it having been checked.

The 0.1mm being conservative does not soften any of this, and you were right to state both
directions and let neither cancel the other. A committed number that is not the contract's
number is a defect at full severity regardless of which way it errs, because the error's
direction was not chosen — it was inherited from a default nobody knew was in force.

### A43. Constant-literal `__import__` does not void the graph. Resolvability is the criterion.

1t's dynamic-import precondition exists because dynamic import can add edges a static graph
cannot see. The hazard is **unresolvable** edges, not the syntactic form of the call.
`__import__("hashlib")` with a compile-time-constant argument is a static import written oddly:
the edge is knowable, it merely requires the instrument to resolve constants.

So the instrument may resolve it, under four conditions:

1. The resolution is **declared as part of the instrument**, general to any constant-literal
   dynamic import, not special-cased to these two sites.
2. The instrument **fails loudly on a non-constant argument** — raises, does not skip. A
   resolver that silently passes over an unresolvable import produces a graph that looks
   complete, which is a plausible in-range result from input it could not handle. It would be a
   member of the class it is auditing.
3. **Positive control before use:** feed it `__import__(variable)` and confirm it raises.
4. The **edge is resolved and followed**, not waived. Do not discharge `hashlib` on the grounds
   that it is stdlib — resolve the edge, follow it, and observe that the target holds no
   fallback site and reaches nothing in the measurement set. Your assessment that it cannot add
   a services edge is a reading, and 1s is explicit that a reading is not evidence. You were
   right to record it rather than act on it; now replace it with a measurement, which is cheap.

The basename collision: yes, package-qualified identity, and it belongs in the same declaration.
It gets a **negative control** — construct two modules sharing a basename and confirm the
instrument distinguishes them. An identity scheme that has never been shown to separate a
collision is not validated at the condition of its reading.

One thing the report does not settle: A35 enumerated `importlib`, `eval`/`exec`, `getattr`
dispatch, decorators and registries, callbacks, and entry points alongside `__import__`. Confirm
the check covered that whole set and not `__import__` alone — and per A41, confirm it was AST
rather than textual, or its zero is a floor.

### A44. The suspension is right. Its label asserts more than you have shown.

Your question is well posed and the answer splits it.

**On the disposition.** You committed `NOT_ESTABLISHED_FIRED_SUBSTITUTION`, which asserts the
substitution fired. What you established is that a credible challenge exists to a row whose
ESTABLISHED status was an affirmative claim — and under 1j that is sufficient to suspend, on its
own, immediately. So the suspension is correct and stays. But the *reason* attached to it states
a finding you have not established, and that matters practically as well as evidentially: if the
branch later proves not to have fired, un-suspending a row labelled FIRED is an improvement
requiring my ruling under 1c, whereas completing a pending determination is not. The wrong label
would have converted a bounded question into an owner escalation.

Re-mark it **`NOT_ESTABLISHED_PENDING_BRANCH_IDENTIFICATION`**. Nothing is rescued by this —
the row suspends either way, the anchor is still gone, and FIRED may well be where it lands.

**On which instrument settles it.** The arithmetic route is primary, and the reason is the
programme's own standing principle: the retained record is the authority and a re-execution is a
reconstruction. If 12.4 uniquely identifies the 1.6 branch, that is evidence from the committed
artifact itself. But it is valid only if **identifiability is established first** — that the map
from `lid_roof_mm` to `lid_roof_underside_z` is injective with everything else held fixed, that
0.1mm exceeds the stored value's precision, and that no other input could produce 12.4. Check
that before reading it, not after.

Compute both branches **using the committed inputs from the retained record**, not today's. If
any other input to the clearance changed between that HEAD and now, today's values contaminate
the arithmetic exactly as they would contaminate a re-execution.

The git-pinned re-evaluation is the fallback where the arithmetic cannot discriminate, and it
carries a weaker status when it stands alone: it establishes a property of the code, not of the
number. Where both are available, run both — agreement is a free negative control on each.

### A45. Recorded

You reverted 45 rather than 43, because the instrument was the same hand-written list for all of
them — the scope correction applied without being asked for a second time. You caught the
basename defect before its clears were used. You recorded the `hashlib` assessment instead of
acting on it, which is 1s working in the one case where acting on it would have been harmless
and therefore tempting. And you stated the 0.1mm in both directions and let neither cancel the
other.

---

## SECTION B — ELEVENTH AMENDMENT

Three clauses. Check labels are free and record any skip without backfilling, as you did with
`1o`.

> **CONTEMPORANEITY OF CITED RECORDS.** A record cited under 1u must be contemporaneous with the
> computation it dispositions. Where it is not, the temporal gap is itself a claim requiring
> disposition — evidence gathered at one code state carries to another only where the relevant
> state is shown unchanged between them.

> **CONSTANT-RESOLVABLE DYNAMIC IMPORT.** A dynamic import whose target is a compile-time
> constant is a static import for 1t's purposes, provided the instrument resolves such imports
> generally, follows the resolved edge rather than waiving it, and raises on any non-constant
> argument.

> **TEXTUAL COUNTS ARE LOWER BOUNDS.** A count produced by a textual scan is a floor, not a
> figure. It may be recorded, but it may not be cited as the size of a class, and any
> disposition resting on the completeness of a textual enumeration is unestablished.

Strictly additive. Bars byte-identical across eleven amendments. Identity moved from
`78eed7f5efe6fba7`. Pin moved and suite run before committing.

---

## SECTION C — THE WORK. NO RENDERS.

1. Re-mark the clearance row per A44, then settle the branch by identifiability and arithmetic
   on retained inputs, with the pinned re-evaluation alongside it if available.
2. A41: re-run the original census under AST, restate 62, and list every other figure in the
   record that came from a text scan with whether it moved.
3. A42: enumerate the contracts, state sweep coverage per contract, reconcile the unswept ones
   by evaluating consumers.
4. A43: declare the resolver with its positive control and the package-qualified rebuild with
   its negative control, confirm the dynamic-import scan's coverage and instrument, then apply
   the graph to the 45.
5. The remaining lookup-default firing audit.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES

- **62 moves under AST** → the allowlist is incomplete, every disposition resting on its
  completeness is unestablished, and the new sites take the audit method. Degradation: commits.
- **62 holds** → the enumeration is established for the first time by a competent instrument,
  and that is a real hardening.
- **An unswept contract yields substitutions** → the contract repair's class-closure claim is
  withdrawn and restated with its actual scope. Every committed number under an unswept contract
  is `NOT_ESTABLISHED_PENDING_RECONCILIATION`. Degradation: commits.
- **Unswept contracts yield zero** → say plainly that the repair's scope was accidentally
  correct rather than checked, and that the check is what closes the class.
- **The arithmetic identifies the 1.6 branch** → `NOT_ESTABLISHED_FIRED_SUBSTITUTION` stands,
  now established, with the record named and contemporaneous.
- **The arithmetic identifies the 1.5 branch** → the row's suspension lifts. That is an
  improvement: **held, not committed**, and placed with me under 1c.
- **The arithmetic cannot discriminate** → the row stays pending, the pinned re-evaluation
  stands alone with its weaker status stated, and neither is reported as settled.

---

## SECTION E — MANIFEST GATING

Held. It releases when the 45 are dispositioned on a validated graph, the lookup-defaults are
audited, the clearance branch is identified, and A41's enumeration and A42's contract sweep both
close. If A42 finds substitutions in a contract that feeds rig geometry, re-plan the manifest
rather than queueing it.

---

## WHAT THIS NODE MAY NOT DO

Move a bar. Repair the `lid_roof_mm` plumbing — it is a declared repair item. Lift the clearance
suspension without my ruling. Discharge an import edge by waiving it. Restore a disposition on a
graph whose controls have not passed. Render anything. Run the manifest. Touch the frozen M5
instrument. Read, echo or commit `.env`.

## BOUNDARY REPORT

The amendment and both identities, pin moved and suite run before the commit. The re-marked
clearance row and the branch identification with its identifiability check stated first. The AST
re-census of 62 and every text-derived figure that moved. The contract enumeration with sweep
coverage and the unswept reconciliation. The resolver and rebuild with both controls. The
dynamic-import coverage confirmation. The lookup-default audit. Whether the manifest releases.
Failures owned. Then, separately, the one thing you are least confident is correct, as a question.
