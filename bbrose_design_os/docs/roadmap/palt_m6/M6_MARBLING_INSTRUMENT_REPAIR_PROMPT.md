# M6 — MARBLING INSTRUMENT REPAIR

Node `04374a1057977dd1`. Follows `M6-CONTRACT-INTEGRITY-REPAIR` (`00288e3` → `9a9fb98`),
law at `399522a75cde1878`. Next in the ruled order.

Owner authorization: transmission of this brief authorizes Section A and the sixth
amendment. Object rather than execute if any of it is wrong.

---

## SECTION A — OWNER RULINGS

### A17. The mid-proof instrument correction was right. Here are the conditions that
prevent it becoming an escape hatch.

You asked whether correcting the proof instrument mid-proof was the frozen text's intent,
or whether the failed byte-compare should have stopped the node the way the marginal
validity reading did — with the risk that you have set a precedent allowing the executor to
re-interpret a frozen proof instrument whenever a control blames the instrument.

Ruling: **correct, and the risk you name is real, so the precedent is hashed with conditions
rather than left as a case.**

Why it differs from the marginal-reading case. There, no control failed; the judgment was
about interpreting a number near a boundary, and it decided verdicts. Here a **null control
failed**: same input to the same code must produce the same result, and an instrument that
reports "different" on that case is falsified by contradiction, without reference to the
hypothesis. Evidence about an instrument obtained from a case whose answer is known a priori
does not require owner adjudication — it requires reporting, which you did.

But you did weaken the instrument. Byte-identity implies pixel-identity and not the reverse.
Weakening a proof standard after it fails, in the direction that lets the proof pass, is the
forbidden pattern. What rescues it is that the removed strength was proven by the control to
carry no information about the claim — container header metadata is not render output — and
that **you narrowed which bits are compared while holding tolerance at exactly zero.**

Hash this as 1k:

> **INSTRUMENT CORRECTION DURING PROOF.** A frozen proof instrument may be corrected by the
> executor, before the verdict is read, only if all five hold:
>
> 1. A **null or tautological control fails** — a case whose correct answer is known
>    independently of the claim under test. Reasoning that the instrument "must be" wrong
>    because the claim is believed true does not qualify.
> 2. The correction is a **narrowing of scope** to the property actually claimed, and the
>    removed scope is proven by that control to carry no information about the claim.
> 3. **Strictness is not relaxed.** Zero tolerance stays zero. Any move from exact to
>    approximate is a bar move and stops the node for owner ruling regardless of how well
>    justified it seems.
> 4. The correction is **declared and committed before the verdict is read.**
> 5. The frozen text is **not re-drafted**; the correction is recorded alongside it with the
>    divergence explained, and reported at the boundary as a first-class item.
>
> If any of 1 through 3 fails, the node stops and escalates.

### A18. The census undercount is a finding about the census method, not about the census

Twenty-five declared, thirty-one actual — the method missed 24%, and you recorded it as an
undercount finding rather than absorbing it, which was right. But the finding is not closed
by being recorded.

The dead-parameter census that produced 49 `DECLARED_NOT_REALIZED` instances was built by
the same static-reachability method. If that method missed six under-declared constants, the
symmetric question is whether it also missed dead parameters — and 49 is not a number to
carry forward on an instrument now known to undercount.

Required in this node, before the marbling work:

1. **Root-cause the six misses.** What structural feature made them invisible — a code path
   the scan did not walk, a naming pattern, an indirection, a family-specific branch? Name
   the mechanism, not the instances.
2. **Re-run the dead-parameter census under the corrected method** and report the new count
   against 49. If the number moves, the `NOT_REALIZED_IN_RENDER_BY_FAMILY` marking moves
   with it, and any parameter newly found dead was until now readable as effective — which
   is the original defect class recurring, and gets recorded as such.
3. If the corrected method finds nothing new, say so — that is a real result and it hardens
   the 49.

### A19. State what the lift permits, and what it does not

`PRODUCT_REALIZATION_BLOCKED → LIFTED` is correct on its pre-committed condition, and I
accept it. But a lifted blocker reads downstream as clearance, and it is not clearance. Four
things still hold: `owner_approved: false`, manufacturing authority `NOT_ESTABLISHED`,
`GATE_2: BLOCKED`, and colour authority absent with every shade
`PROVISIONAL_VISUALIZATION_SHADE`. The three diffuse verdicts remain unestablished.

Write a scope statement into the lift record itself, in plain language: what work the lift
now permits to begin, and the explicit list of what a product still cannot do — ship, be
quoted to a client as final, or have any shade treated as colour authority. Anyone reading
`LIFTED` six weeks from now must hit that sentence before they can misread it.

### A20. The anti-reroll guard's first live test — noted

FAIL → FAIL, nothing to bank, and the chroma span moving 0.005 → 0.0213 in exactly the
direction the named parameter predicts, attributed to census L305 before re-measurement.
That is the guard doing precisely what it was declared for, on the first occasion it could
have been embarrassing. Recorded.

---

## SECTION B — THE MARBLING INSTRUMENT REPAIR

### B1. The standing diagnosis

`SOLID_VS_MARBLED` FAILs on two owners. The contract half is discharged: the derivation is
genuinely chromatic per C6 and the span moved 4×. The instrument half is this node: both
marbling axes are floor-ineligible on their own noise — 0.418 / 0.697 originally, and the
chroma axes now read 0.81 / 1.13, which is worse.

A floor above 1.0 on a relative-effect axis means the instrument's response to nothing
exceeds any effect it could ever report. The axis is not noisy; it is not measuring the
thing.

### B2. My hypothesis, to be tested and not adopted

Marbling is a **stochastic spatial pattern**: the vein layout is itself seeded. A statistic
computed over spatially-registered fields will therefore see a total pattern change between
any two seeds, and will report that as effect. The seed-only floor is then enormous by
construction — the instrument is measuring vein placement, which the seed controls, rather
than material chromaticity, which the family controls.

If that is right, the remedy is a statistic **invariant to vein placement**: a distributional
reading of chroma over the field — quantile spread, histogram distance, per-channel
dispersion — rather than any spatially-registered comparison. That is an instrument repair,
not a bar move, and it is exactly the standing rule of fixing the instrument rather than
lowering the requirement.

I may be wrong. Test it: measure the seed-only floor of a placement-invariant statistic and
compare it against the registered one. If placement-invariance does not collapse the floor,
my diagnosis is wrong and the cause is elsewhere — report that plainly and diagnose again
before building anything.

### B3. Designing a statistic after a FAIL — the same guard as substitution

Inventing a new measurement after the old one failed is cherry-picking unless it is fixed in
advance. Per A14's pattern:

> **Name every candidate statistic before measuring any of them.** Measure all. Report all
> floors and all effects, including the candidates that fail. A candidate qualifies only if
> it passes both controls below, and the choice among qualifying candidates is made by
> declared criteria written before the numbers, not by which one produces a PASS.

Two controls, both mandatory, both declared before measurement:

- **Negative control.** The statistic must **fail to distinguish** two marbles of identical
  material at different seeds. A statistic that separates same-material seed variants is
  measuring the seed.
- **Positive control.** The statistic must **distinguish** a marble from a material known to
  differ chromatically — a live fixture, not a synthetic one, per the precedent you set with
  the glitter blindness check.

A candidate failing either is discarded and recorded as discarded.

### B4. What a repaired instrument does and does not entitle

If a qualifying statistic is found, `SOLID_VS_MARBLED` is **re-ruled, not restored**. It
must clear its bar on the new axes, with two axes independent under the full amended law —
census condition, driver condition, adequacy precondition, burden rule, all of it. A new
instrument does not inherit the old one's verdict, and it does not inherit an establishment
status either: its readings are `NOT_ESTABLISHED_PENDING_SPREAD` until its own declared
ensemble is measured, which under the ruled order is later work.

If the re-rule lands FAIL, it is recorded as FAIL. If no qualifying statistic exists, that is
recorded too: the marbling family cannot currently be distinguished by any commissioned
instrument, which is a fact about the rig suite and goes on the record as one.

---

## SECTION C — SEQUENCE AND AMENDMENT

Sixth amendment, hashed before any measurement: 1k (A17), plus A13's
`UNMET_BY_CONSERVATIVE_PROXY`, A14's substitution rule and A15's partial-replicate law if
the fifth amendment did not already carry them — check rather than assume. Strictly
additive, bars byte-identical, identity moved from `399522a75cde1878`, chain recorded.

Then A18, then A19, then Section B.

## WHAT THIS NODE MAY NOT DO

Move a bar. Relax a tolerance. Re-draft a frozen declaration. Rescue a verdict. Choose a
statistic by its outcome. Start `M6-DECLARED-ENSEMBLE-SPREADS`, `M6-CENSUS-REPLICATE`,
`M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION`, `M6-FLOOR-STATISTIC-REPLICATE` or
`M6-FROZEN-INSTRUMENT-DEFECT-REGISTER`. Touch the frozen M5 instrument. Read, echo or commit
`.env`.

## BOUNDARY REPORT

1k and both identities. The A18 root cause, the re-run dead census, and whether 49 moved.
The A19 scope statement verbatim. The candidate statistics named before measurement, all
their floors and both controls' results including the discards, and the declared criterion
by which the winner was chosen. The re-rule of `SOLID_VS_MARBLED` with its establishment
status. Failures owned. Then, separately, the one thing you are least confident is correct,
as a question.
