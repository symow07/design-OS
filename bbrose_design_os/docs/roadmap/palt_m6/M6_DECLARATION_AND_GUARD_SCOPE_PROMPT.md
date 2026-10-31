# M6 — DECLARATION AND GUARD SCOPE

Follows `M6-SCOPE-AND-PROVENANCE` (`e35d2ba` → `937b6d3`), law at `bf53ca5a9eeeab4d`.
No renders. Your question dissolves rather than needing a new claim type, and the answer
reclassifies fourteen sites and re-reads a result already in the record.

Owner authorization: transmission authorizes Section A and the twelfth amendment.

---

## SECTION A — RULINGS

### A46. Not a third claim type. You named the wrong claim.

You asked whether "declaredness of a default" needs its own instrument, and you were right that
no instrument in the law is competent for *"this default is the declared behaviour"* — because
that is a claim about intent, and intent is unfalsifiable. There is no instrument for it and
there should not be one.

But that is not the claim the disposition needs. Compare the two cases as records rather than
as intentions:

- **`lid_roof_mm`** — the contract declares 1.5, the code defaults to 1.6. Two declarations
  exist and they **disagree**.
- **`r.get("samples", 64)`** — either a contract declares `samples` and agrees, or no contract
  declares it at all.

The defect in `lid_roof_mm` was never "a default exists." It was **conflict between records**.
And conflict between records is mechanically checkable, falsifiable, and cheap — it is the same
instrument that caught it, pointed at the whole key set instead of one key.

So the partition, which replaces your reading of intent entirely:

- **`DECLARED_AGREEING`** — a contract declares the key, the code default matches it.
- **`DECLARED_CONFLICTING`** — a contract declares the key, the code default differs. Defect,
  at `lid_roof_mm`'s severity.
- **`UNDECLARED_DEFAULT`** — no contract declares the key. The code default is the only
  statement of the value anywhere.

Re-run the 14 through that partition. Nothing about intent is asked and nothing is read.

### A47. Your third case is already ruled, at A23 — and it re-reads A37's "zero overlap"

You asked whether declaration-by-construction is sufficient. **No, and this programme ruled it
eight nodes ago.** A23 disposed of the identity-zero `distortion` constant relied on at seven
sites, and the ruling was: declare it rather than exempt it, because *"an undeclared constant
whose value happens to be inert today moves seven sites silently if anyone ever changes it, and
'it is currently zero' is a fact about the value, not about the contract."*

A default sitting in committed code is a fact about the value, not about the contract. So every
`UNDECLARED_DEFAULT` among the 14 is a **`BUILDER_CONSTANT`** — the standing mirror class of
`DECLARED_BUT_UNREALIZED` — wearing a different syntax. It needs no new claim type. It needs the
disposition its class already has.

Which forces a re-reading of a result you reported as clean. A37 found **zero overlap** between
the 28 lookup-defaults and the 49 dead parameters and 25 under-declared constants, and that was
recorded as a negative result. Under this ruling it is not reassurance — it is **evidence that
the two censuses have disjoint blind spots.** A lookup-default *is* a builder constant hiding a
literal inside a call, so a census that found 25 of them and none of these was looking for a
syntactic shape rather than for the class. That is A18's mechanism for the third time.

So: **25 is probably a floor.** Re-run the under-declared census with lookup-defaults, class
attributes, environment reads and default arguments in scope, and restate it. If it does not
move, that hardens 25 properly for the first time.

### A48. Guard scope has now failed three times. It stops being a question and becomes a test.

Count them. A22 — the third-appearance guard scoped to rank correlations, missing analysis
tooling. A34 — reachability established by a hand-written module list rather than an instrument.
A41 — the guard test textual, missing 68% of its own population. Three appearances of the same
class: **a declared structural guard whose detector does not cover the class it claims to
protect.**

1q made "does the guard cover the class?" a question to ask. The standing rule for a class
returning a third time is that it gets a structural guard, and a question asked by a person is
not one. Build it:

> Every declared structural guard carries a **seeded corpus** — a versioned set of synthetic
> instances spanning every known shape of the class it protects. The suite fails if the guard's
> detector misses any corpus member. Adding a newly-discovered shape to the class means adding
> it to the corpus in the same commit as the discovery.

That turns "what is the class" from prose into a versioned artifact, and it makes coverage a
thing the suite checks rather than a thing an executor remembers. Seed it now with every shape
this arc has surfaced, including the line-break case and whatever explains the 62 → 194 gap.

### A49. Three things the report asserts more cleanly than it establishes

**The composition argument holds, under a condition you left implicit.** "No incoming edge from
the measurement closure, so outgoing unknowns cannot add closure-side edges" is sound — an
unreachable node cannot lie on a reachable path. But it is sound **only if the closure itself
contains zero unresolvable imports**, since one of those could create the incoming edge the
argument denies. State that condition and confirm it holds, rather than leaving the argument
resting on it silently.

**Entry-point loading is an import question, not a call-graph one.** You grouped entry points
with `getattr` dispatch, registries and callbacks as call-graph concerns the instrument does not
claim. Callbacks and `getattr` dispatch, yes. But plugin or entry-point loading resolves and
imports a module *by name at runtime*, which is an edge the import graph should have and cannot
see. One check: does anything in the closure load modules via entry points or a name-keyed
registry? If yes, that is a hole in the instrument, not outside its claim.

**"Rig contracts scope-bounded to their commissioning identities" is an exemption.** It reads as
a fact and functions as an exclusion from the consumer-evaluation that found the only
substitution in the sweep. Under 1r an exemption is an affirmative claim of inertness carrying
the burden of establishment. Either consumer-evaluate the rig contracts as you did case, pan,
owner-intent and layout, or disposition the exemption with evidence. Given the rig contracts feed
measurement directly, I would rather you just evaluated them.

### A50. Recorded

Your first graph run gave the unresolvable module empty edges — a graph that looks complete,
which is condition 2 of the resolver ruling firing on the resolver itself. Caught before any
clear was committed. And the clearance branch closed with two independent instruments agreeing,
each serving as the other's negative control, with identifiability stated before the reading
rather than after. Both are the discipline working.

---

## SECTION B — TWELFTH AMENDMENT

> **DECLARATION IS INDEPENDENT OF SYNTAX.** Any value that reaches a render or a measurement and
> is not stated in a contract is an undeclared constant, regardless of the mechanism by which it
> enters — literal, default argument, lookup default, class attribute, environment read or
> fallback. Where a contract does state the key, a differing in-code value is a conflict and a
> defect. Declaration-by-construction is a fact about the value, not about the contract.

Plus A48's guard-corpus requirement. Strictly additive, bars byte-identical across twelve
amendments, identity moved from `bf53ca5a9eeeab4d`, pin moved and suite run before committing.

---

## SECTION C — THE WORK, IN THIS ORDER. NO RENDERS.

**Reachability before behaviour.** Do not behaviour-disposition 194 sites. Run the validated
import graph across the full 194 first; most will clear structurally, and only the survivors —
sites reaching a committed number — need per-site behaviour dispositions. Report both counts, so
the reduction is visible.

1. The 14 through A46's partition; the `UNDECLARED_DEFAULT` ones marked `BUILDER_CONSTANT`.
2. The under-declared census re-run per A47, with 25 restated.
3. The guard corpus built and seeded; the suite failing on a missed member.
4. A49's three items: the composition condition confirmed, the entry-point check, the rig
   contracts evaluated.
5. Reachability across 194, then behaviour on the survivors.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES

- **A key in the 14 proves `DECLARED_CONFLICTING`** → second live substitution, at
  `lid_roof_mm`'s severity, with its committed numbers suspended. Degradation: commits.
- **25 moves** → the under-declared census was scoped to syntax rather than class, recorded as
  A18's mechanism recurring a third time, and every figure resting on 25 is restated.
- **25 holds** → say so; it is the first competent enumeration of that class.
- **The guard corpus catches a shape the current detector misses** → the detector was inadequate
  at declaration time and every count it produced is restated. Degradation: commits.
- **A rig contract yields a substitution** → it feeds measurement directly, so affected committed
  numbers suspend and the manifest re-plans.
- **Reachability clears most of the 194** → say the number plainly. A large structural clear is a
  real result and it is what should happen if the codebase is mostly not measurement code.

---

## SECTION E — WHERE THIS ARC ENDS

State the stopping condition in the record, because five nodes of auditing have accumulated and
the end of it should be legible rather than implied. **This arc closes when three things hold
simultaneously:** the enumeration is complete by an instrument competent to claim completeness;
every enumerated site reaching a committed number carries a behaviour disposition; and the guard
carries a corpus demonstrating it covers the class. After that, a new instance is caught by the
guard on the commit that introduces it, and never again by an audit node.

Report against those three at the boundary, so the distance left is a number rather than a
feeling.

## MANIFEST

Held, on: the 30 reachable `NOT_ASSESSED`, the 194's survivors, the 12 `TO_TRACE` sites awaiting
A38 wiring, and the `lid_roof` repair item. The case contract feeds rig geometry and its
substitution is established, so re-planning must decide whether the clearance-adjacent renders
move — that decision belongs to the manifest node, not this one.

## WHAT THIS NODE MAY NOT DO

Move a bar. Repair `lid_roof_mm` or any lookup-default — repairs are their own declared node.
Behaviour-disposition sites the graph has not first been run against. Exempt a contract by
argument. Render anything. Run the manifest. Touch the frozen M5 instrument. Read, echo or commit
`.env`.

## BOUNDARY REPORT

The amendment and both identities, pin moved and suite run before the commit. The 14 partitioned.
The re-run under-declared census and whether 25 moved. The guard corpus with its seeded shapes
and a demonstration that the suite fails on a missed member. A49's three items. The 194 reduced by
reachability, with survivors behaviour-dispositioned. The Section E three-part distance. Failures
owned. Then, separately, the one thing you are least confident is correct, as a question.
