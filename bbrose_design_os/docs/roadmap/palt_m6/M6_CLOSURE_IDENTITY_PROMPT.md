# M6 — CLOSURE IDENTITY

Follows `M6-CLASS-SCOPE-CLOSURE` (`a7cd131` → `9fc7299`), law at `ec7c6439a96c24b9`.
No renders. Your question is right and the law already answers it. But one clause in this report
is carrying far more weight than its position suggests, and it goes first.

Owner authorization: transmission authorizes Section A and the fifteenth amendment.

---

## SECTION A — RULINGS

### A64. The characterization chokepoint. Take this out of the list and give it its own line.

You wrote, in a per-site enumeration: *"the characterization chokepoint transits every powder
measurement record — its site closes forward via the trace at the manifest and stays open backward
for already-committed numbers."*

Read that as a statement about the establishment table. A site that transits **every powder
measurement record** means every committed powder number has that site in its chain. Its backward
direction is therefore not a residue; it is universal. Delivered mildly in a list of four, it is
the largest open item in the arc.

The question that settles it is narrow and answerable today: **was that site among the 383
computations the fallback-firing audit covered?**

- **If it was audited** — its backward direction closed then, the finding is that the audit's
  coverage was better than this report credits, and the establishment table's hardening stands as
  written.
- **If it was not** — and it plausibly was not, since it may be one of the 132 sites the 62 → 194
  restatement added — then the hardening recorded at the fallback-firing audit is **qualified**.
  That node concluded every committed number was computed on a live denominator; that was
  established for `_effect` denominators across the sites then enumerated, not for this site. Say
  so explicitly and restate the hardening with its actual scope.

If it was not audited, audit it now by the same method — retained records, no renders — rather than
waiting for the trace, because the trace is prospective and cannot reach the already-committed
numbers this site transits.

### A65. Scoped, and 1t already says so. Make the closure an identity rather than a column.

`INERT_BY_UNREACHABILITY` was never absolute. 1t's own text discharges a site *"not import-reachable
from any measurement entry point"* — the discharge is relative to an entry-point set by
construction, and 2d makes the consequence explicit. So the 638 are discharged for the powder
closure and pending for any other.

Two columns is the right instinct and the wrong shape, because it assumes there will only ever be
two programmes. Do it the way this programme does everything else:

> An unreachability discharge **names the closure it was computed against, and that closure carries
> an identity.** `INERT_BY_UNREACHABILITY[closure=<name>@<hash>]`. The hash covers the entry-point
> set. If the entry points change, the identity moves and every discharge computed against the old
> one is visibly stale rather than silently wrong.

That costs nothing now, generalises to any future programme without a schema change, and makes a
stale discharge detectable by comparison rather than by memory. It is the law-identity chain
applied one level down, which is where it belongs.

The layout node's first task is then exactly what you said: enumerate the layout entry points and
recompute. Note this is needed regardless of that audit's priority, because the 638 ledger is
incomplete without it.

### A66. Three readings, three corrections, all in the same direction. That is a bias, not a run of luck.

A29 — informal reading of the two handlers. A34 — reachability by hand-written module list. A58 —
name-reading the 36, overturned into 28. Every one of them was corrected by an instrument, and
**every correction went the same way: the reading was more permissive than the instrument.**

The mechanism is not mysterious and it is worth naming in the register: reading code tells you what
the code is *for*, and purpose is systematically narrower than reachability. A module named for
layout is *for* layout; what it can reach is a different question and always a larger set. So a
discharge established by reading is permissive by construction.

Bounded consequence, and I want the count before any re-work: **enumerate every discharge, exemption
and exclusion currently in the record that was established by reading rather than by an instrument.**
Count only, name them, and do not re-establish anything in this node. If the list is short — and it
may well be, since most dispositions in this arc were instrument-based — the follow-up is trivial. If
it is long, it is its own node.

### A67. The 149 and the 43 need their own join

26 + 638 + 149 = 813, and the 149 are in-reach and un-dispositioned. The site-level figure is 43. So:
**how many distinct sites do the 149 keys map to, and is that set exactly the 43?**

If it is 43, the two ledgers are consistent and both stand. If it is more than 43, the site-level
class distance is understated and moves again. Keeping the ledgers unmerged is correct; checking them
against each other is a different obligation and it is the one 1u is for.

### A68. The layout audit runs alongside, not ahead. My call, with a trigger.

You stated the evidence and left the decision, which is right. Deciding:

Those records gate dieline and case geometry on the physical-output path, so the severity argument is
real — but nothing ships today with `GATE_2: BLOCKED` and manufacturing authority `NOT_ESTABLISHED`,
so there is no live physical risk to race. And the audit **renders nothing**, which means it does not
compete with the manifest for the scarce resource. That is precisely the disposition
`M6-FROZEN-INSTRUMENT-DEFECT-REGISTER` got in the ruled order: *"a documentation and decision node
with no render cost — slot it wherever a render queue is occupying the machine."* Same reasoning, same
answer.

So: `M6-LAYOUT-FALLBACK-AUDIT` is not reprioritised ahead of the manifest; it is slotted to run while
the render queue occupies the machine. Its entry-point enumeration should happen early regardless,
because A65 needs it.

**Pre-committed trigger:** if that audit finds a `FIRED` site on the dieline or case-geometry path, it
escalates to me immediately rather than waiting for its node to complete. A firing on the
physical-output path is not a finding that waits for a boundary report.

### A69. Recorded

You ordered your own routing overturned by running the check I asked for, reported the manifest
distance going 7 → 35 with the number first, and named it as 1s's own defect in your work. And you
noted the overturned chain is the same chain `lid_roof_mm` fired on — which makes the result
consistent rather than surprising, and is the kind of connection that is easy to leave out because it
makes the earlier error look more avoidable.

---

## SECTION B — FIFTEENTH AMENDMENT

A65's closure-identity clause. Strictly additive. Bars byte-identical across fifteen amendments.
Identity moved from `ec7c6439a96c24b9`. Pin moved and suite run before committing.

---

## SECTION C — THE WORK. NO RENDERS.

1. A64 first. Was the chokepoint site in the 383? Restate the fallback-audit hardening with its
   actual scope, and audit the site from retained records if it was not covered.
2. Re-key the 638 with closure identity; enumerate the layout entry points so the second closure can
   be computed.
3. A66's enumeration — count and name, re-establish nothing.
4. A67's 149 → sites join.
5. Then stop. `M6-LID-ROOF-REPAIR` is next.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES

- **The chokepoint was not in the 383** → the fallback audit's hardening is restated with its real
  scope, and every powder committed number is backward-open on that site until it is audited.
  Degradation: commits immediately, and it is reported at the top of the boundary report, not in a
  list.
- **The chokepoint was in the 383** → the hardening stands and the backward direction on that site
  closes. Say so plainly.
- **The 149 map to more than 43 sites** → class distance moves and both ledgers restate.
- **A66's enumeration is long** → it becomes its own node and the manifest is not held for it, since
  a permissive discharge that has stood this long does not become urgent by being counted.
- **Layout entry points reach sites currently discharged for powder** → those keys carry the second
  closure as pending, not as discharged, and the layout audit's scope grows accordingly.

---

## SECTION E — DISTANCES

Three now, each with its instrument named: **class 43**, **manifest 35**, **key-level ledger 149
in-reach**. Report all three. Do not merge any of them, and state the consistency check between the
first and third.

## MANIFEST

Unchanged in sequence: this node → `M6-LID-ROOF-REPAIR` → manifest, with `TO_TRACE` wiring in the
manifest's own declaration. The manifest's gate now carries 35 rather than 7, and those 35 are
dispositioned by the audit method already proven at zero render cost.

## WHAT THIS NODE MAY NOT DO

Move a bar. Repair `lid_roof_mm`. Re-establish A66's reading-based discharges — count them only.
Discharge the chokepoint by the prospective trace. Render anything. Run the manifest. Touch the
frozen M5 instrument. Read, echo or commit `.env`.

## BOUNDARY REPORT

A64's answer first, before the amendment. Then the amendment and both identities. The re-keyed 638
with closure identities and the layout entry-point enumeration. A66's count with names. The 149 → 43
join. The three distances. Failures owned. Then, separately, the one thing you are least confident is
correct, as a question.
