# M6 — ALLOWLIST COVERAGE CLOSURE

Follows `M6-FALLBACK-FIRING-AUDIT` (`e36e95e` → `2bd5b7d`), law at `eaa03824272b1075`.
Small node. No renders. It closes the last two open dispositions and the coverage question
underneath the other sixty, then releases the 102-render manifest.

Owner authorization: transmission authorizes Section A and the ninth amendment.

---

## SECTION A — RULINGS

### A29. Your symmetry argument fails, and why it fails is the ruling

You asked: if reading the surrounding code is not good enough to prove those two handlers
inert, is it good enough to prove them irrelevant? Taken as stated the argument is airtight,
and you were right to distrust the position you had landed in. It fails anyway, because the
two claims are not the same *kind* of claim and do not take the same instrument.

- **"It never fired"** is a claim about what happened at runtime, in the past, on particular
  inputs. No amount of reading the source can settle it. That is what 1r means and your
  `NOT_ASSESSED` on that question is correct.
- **"No committed number is downstream of it"** is a claim about the structure of the
  program. Static analysis is not a weak instrument for that claim; it is the *appropriate*
  instrument for it, and this programme already relies on it — the dead-parameter census is
  a static reachability instrument and its count of 49 is a committed number.

So reading code is bad evidence for the first claim and, in principle, good evidence for the
second. What you actually did was neither: you used **informal** reading where the programme
has a **corrected and hardened** instrument sitting right there. You reached a defensible
conclusion by an undeclared route, and under this programme's own rules you do not get to
keep a conclusion because it happens to be right. Re-derive it with the declared instrument.
It costs nothing and it converts a judgment into a record.

Note also the reductio that makes blanket propagation the wrong answer. If those handlers
wrap render calls, then *every* render-derived statistic in the programme is downstream of
them, and propagation would mark essentially every committed number not-established. A status
that lands on everything discriminates nothing; that is not caution, it is the abandonment of
the establishment table. 1j's burden rule exists to sort claims, not to flatten them.

And the substantive point is sharper than "it is an IO path." **A handler that re-raises
cannot contribute a value to any computation, because its firing terminates the computation
rather than completing it with a plausible number.** Firing produces no number, not a wrong
one. The entire disposition therefore reduces to one bounded, static, checkable question:

> Does **every** path out of each handler either re-raise or return no value that reaches a
> computation?

Every path, not the common one. Answer that with the census instrument and the entries close.

### A30. Coverage of the audit is itself an affirmative claim — check the sixty

You cited the audit as evidence for 60 `INERT_PROVEN`. The audit covered 383 computations.
The 62 are *sites*. For a site to be proven inert by the audit, that site's guard must have
been **evaluated in at least one audited computation with a recovered denominator**. A site
that appears in zero audited computations is not shown inert by the audit; it is merely
absent from it, and absence from the audited set is not evidence of anything.

This is A25 recurring one level up. The allowlist was an affirmative claim about 62 sites;
"the audit proves them" is an affirmative claim about the audit's coverage of those sites,
and it has the same burden.

So: for each of the 60, name at least one audited computation in which that site was
evaluated, with its recovered denominator. Any site with zero evaluations leaves
`INERT_PROVEN` and takes the same route as the two handlers — established statically or
`NOT_ASSESSED`. I expect this to move a small number, possibly none. If it moves none, say
so; that is a real result and it hardens the sixty properly rather than by assumption.

### A31. The census scanned for shape. 1r dispositions on behaviour. That gap is not free.

A22 commissioned a scan for four shapes: default-on-lookup-failure, bare or over-broad
`except`, silent type coercion, index/mask conflation. 1q defines the class by behaviour: *an
operation that, given malformed, absent or unexpected input, silently produces a plausible
in-range result instead of raising.*

A bare `except:` that re-raises is over-broad in shape and is not a member of the class in
behaviour. If that is what those two handlers are, their correct disposition is not
`NOT_ASSESSED` — it is **`NOT_IN_CLASS`**, and the same test may move others among the 62.

This matters for the register, not for safety. "62 instances of `SILENT_PLAUSIBLE_FALLBACK`"
is a committed claim about the size of a defect class, and a class size inflated by shape
false-positives is a wrong number in the defect record. Report the corrected class size with
both figures — scanned shapes, and confirmed class members — and keep the distinction visible.

### A32. The direction that actually worries me is false negatives, and it is bounded

A shape scan that produces false positives will also produce false negatives: a fallback that
silently returns a plausible in-range value without matching any of the four shapes is
invisible to the guard test, and the guard test is what A22 declared as the structural
protection. A18 already ruled that a static instrument's misses are a finding about the
*method*, and that ruling applies here without modification.

Name the mechanism, not instances. Candidate shapes the four do not cover, to be checked and
extended rather than adopted: `dict.get(k, default)` and `getattr(o, n, default)`; `or`
short-circuit defaults (`x = compute() or 0.0`); `np.nan_to_num`, `.fillna()`, and clipping or
clamping that silently maps out-of-range to in-range; `np.errstate` or warning suppression
around a division; **NaN or inf produced by an unguarded division and then consumed by a
comparison**, where `nan > threshold` and `nan < threshold` are both False and the direction
of the resulting error depends on which way the comparison is written; and mutable or
computed default arguments consumed as values.

**Bound this so it does not become a treadmill.** Count only. Name the shapes, extend the
guard test to them, report the instance count and where the instances live — measurement code
or not. Disposition nothing beyond counting. If the count is material, dispositioning is its
own node and it uses Section C's method from the last node, which is now proven cheap.

State the stopping condition explicitly: the sweep stops when the scan is shown to cover the
class **as 1q defines it**. Further expansion after that requires naming a new class, not
adding more shapes to this one.

### A33. The recovered denominators can answer a second question for free, and it is not the
one you asked

Your `NEAR_FIRING` band was declared against the guard, and it did that job — 1e6 above the
threshold, one number applied identically to every class so none could be exempted after
seeing its data, justified on three independent grounds before anything was computed. That is
the discipline working, and the "one number, every class" construction is the part I want
repeated.

But "did not fire" and "was well-conditioned" are different properties. `_effect = |a − b| /
mean` on a denominator of 0.004656 is nowhere near the guard and is also a ratio of two
quantities sitting close to the standing R2 realization floor of 0.002. A ratio of two
barely-realized operands inherits their noise and is not the same statistic as a ratio of two
well-realized ones — it can be perfectly safe from the fallback and still be a number whose
precision does not support a 0.25 bar.

You now hold every denominator. So report their distribution: percentiles across all 383, the
lowest twenty named with their axis, their consumer class, and the committed numbers they
feed. Then flag any committed effect whose operands sit within a declared factor of the
realization floor as a **conditioning** finding — declare that factor before computing it, as
you did the last one.

No verdict moves on this. It is a fragility record of the same kind as `NEAR_FIRING`, and it
is honest about being a question rather than a result: whether operand precision at that scale
actually threatens the bar is measurable from data you already have, and it may well come back
showing it does not.

---

## SECTION B — NINTH AMENDMENT

Hash A29's instrument-competence rule. If `1s` is occupied, record the collision and tell me
rather than absorbing it, as you did with `1n`.

> **INSTRUMENT COMPETENCE BY CLAIM TYPE.** A disposition that discharges an entry from an
> allowlist, exemption or suppression separates into two claims, each requiring an instrument
> competent for its type: **historical** (did it fire), which no static reading can settle,
> and **structural** (can any committed number be downstream of it), which static analysis
> can. A structural discharge is permitted only if all five hold:
>
> 1. It is established by a **declared** static instrument of record, not by reading
>    surrounding code.
> 2. It is a claim about **every** path out of the site, not the typical one.
> 3. It claims **unreachability of any committed number** — not that firing is unlikely, not
>    that firing would be harmless.
> 4. If the instrument cannot decide, the entry stays `NOT_ASSESSED` and inherited status
>    propagates to the numbers actually downstream of it.
> 5. It is recorded as **`INERT_BY_UNREACHABILITY`**, distinct from `INERT_PROVEN`, so that
>    entries resting on structural evidence are separable from entries resting on runtime
>    evidence.
>
> Condition 5 is load-bearing: the static reachability instrument has been found to undercount
> once already, and if it is found to undercount again, the structurally-discharged entries
> are exactly the set that reopens.

Strictly additive. Bars byte-identical across nine amendments. Identity moved from
`eaa03824272b1075`. Pin moved and suite run **before** committing.

---

## SECTION C — CLOSE THE OPEN ENTRIES. NO RENDERS.

1. Run the corrected census instrument against the two handlers and against any site A30's
   coverage check leaves without an audited evaluation. Report per site: every exit path, what
   each returns or raises, and whether any committed number is downstream.
2. Disposition each as `INERT_BY_UNREACHABILITY`, `NOT_IN_CLASS`, or `NOT_ASSESSED`.
3. For anything left `NOT_ASSESSED`, propagate inherited not-established status to **the
   numbers actually downstream of that site**, enumerated. Not to the establishment table
   wholesale.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES. WRITTEN BEFORE SECTION C RUNS.

- **Both handlers discharge structurally** → allowlist closes at 62 dispositioned, nothing
  propagates, the establishment table hardens further. Say plainly that two entries rest on
  structural rather than runtime evidence and name them.
- **A handler cannot be decided** → its downstream numbers are enumerated and marked
  not-established. If that set includes any floor or seed-only computation, the manifest
  re-plans. Degradation: commits immediately.
- **A30's coverage check moves entries out of `INERT_PROVEN`** → they route through Section C
  and the sixty is restated with the corrected figure. Degradation: commits immediately.
- **A31 finds `NOT_IN_CLASS` members** → the defect register's class size corrects downward,
  with both figures kept. This is a correction to a record, not an improvement to a verdict,
  and it commits.
- **A32's extended scan finds new instances in measurement code** → count and locate them,
  disposition nothing, and the manifest holds pending a firing audit on the new set.
- **A32's extended scan finds nothing, or nothing in measurement code** → say so plainly. That
  is the result that closes the class.

---

## SECTION E — MANIFEST RELEASE

If Section C closes both handlers, A30 moves nothing out of the sixty, and A32 finds no new
measurement-code instances, the 102-render combined manifest is **released** and is the next
node, as planned, with its per-member resumable boundary.

If any of those three moves, re-plan before queueing rather than mid-queue.

---

## WHAT THIS NODE MAY NOT DO

Move a bar. Repair a fallback site — dispositioning is not repairing. Disposition A32's new
instances. Commit an improvement. Render anything. Propagate not-established status to numbers
not actually downstream of an undecided site. Touch the frozen M5 instrument. Read, echo or
commit `.env`.

## BOUNDARY REPORT

The amendment and both identities, pin moved and suite run before the commit. The Section C
dispositions with every exit path named. A30's coverage result — how many of the sixty had an
audited evaluation, and what moved. A31's corrected class size, both figures. A32's named
shapes, the extended guard test, the instance count and where they live. A33's denominator
distribution, the lowest twenty, the declared conditioning factor stated before its results.
Whether the manifest releases. Failures owned. Then, separately, the one thing you are least
confident is correct, as a question.
