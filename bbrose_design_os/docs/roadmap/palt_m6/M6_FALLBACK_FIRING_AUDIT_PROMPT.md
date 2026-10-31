# M6 — FALLBACK FIRING AUDIT

Follows `M6-CONTROL-COVERAGE` (`214ef1f` → `95cddef`), law at `c56a57b82bc3e36e`.
Gates the 102-render manifest. No renders in this node — everything from retained records.

Owner authorization: transmission authorizes Section A and the eighth amendment.

---

## SECTION A — RULINGS

### A25. Yes. The allowlist is an affirmative claim and nothing established it.

Your question answers itself against a rule already in the law. An allowlist asserts that 62
sites are inert. That is an affirmative claim, and 1j places the burden of establishment on
the affirmative claim. "Repairing them moves committed numbers" is a reason not to repair
them yet; it is not evidence that they never fired.

The triage specified three questions per site — can it fire under inputs the code actually
receives, has it ever fired judged from retained records, and which committed numbers passed
through it. The allowlist answered only the first and a different question about repair cost.
Questions two and three are outstanding, and they are answerable today from retained data
without a single render.

You caught this yourself, which is the third time in this arc that the executor has surfaced
the defect in its own work before anyone asked. Recorded.

### A26. The directional asymmetry, which does not run the way it first appears

`_effect = |a − b| / mean` returning 0.0 on a near-zero denominator reads as "no effect."
Where that lands depends entirely on which comparison consumed it:

- **In a clearing comparison** — 0.0 is below the bar, so a fired fallback pushes toward
  FAIL. Self-limiting, and it cannot manufacture a PASS.
- **In a floor or seed-only noise computation** — a fired fallback makes the axis look
  quieter than it is. That lowers `required_clearing_effect`, grants eligibility that was
  never earned, and every clearing measured against that floor inherits the error. This
  direction manufactures PASSes, and it sits underneath the entire eligibility machinery.
- **In a census rank vector** — a fired fallback injects a 0.0 that changes ranks, and every
  R5 independence reading computed from that vector is affected.

Partial protection exists on the floors and must not be mistaken for a clean bill:
`max_seed_only_effect` is a maximum over 15 pairings, so a single fired fallback cannot pull
it down. It takes near-total firing to move a maximum. That is a reason the floors are
probably safe and not a reason to skip checking them — the small floors in particular
(`GRAZING_BAND_CONTRAST` 0.00651, `HIGHLIGHT_PEAK` 0.00797, `SPECULAR_TO_DIFFUSE_RATIO`
0.00886) are exactly the shape a heavily-firing denominator would produce, and the innocent
explanation and the guilty one predict the same number.

### A27. The allowlist becomes tri-state. Amnesty is not a status.

Every one of the 62 entries takes one of:

- `INERT_PROVEN` — shown on retained data never to have fired, with the evidence cited.
  Stays allowlisted. Still fixed to raise eventually, under the declared repair node.
- `FIRED` — fired at least once in a computation that reached a record. Not allowlisted;
  enters the repair node with an explicit void list of the numbers it touched.
- `NOT_ASSESSED` — retained data insufficient to tell. Blocks nothing by itself, but every
  committed number downstream of it inherits `NOT_ESTABLISHED_PENDING_SPREAD`'s sibling
  status: not established, because a value in its computation chain is unverified.

An entry may not sit in the allowlist without one of these.

### A28. Your C2 correction is accepted; my claim was wrong

The rig's floor ensemble is warm-shade MARBLED at seeds 500–505 (L183–192), the warm negative
control exists and holds at 0.0548, and my brief asserted otherwise. Your narrower finding is
the correct one and is better stated than mine: 1p's every-member clause exposes that the
**solid member's seed-stability was never measured**, because the ensemble is all-marbled.
`SOLID_VS_MARBLED` FAIL at qualifier count 1-PENDING is right, and the pending item is a
bounded manifest entry rather than a missing control.

Record the correction against my brief, as you did with the calendar.

---

## SECTION B — EIGHTH AMENDMENT

Hash A27's tri-state allowlist discipline, and this general rule with it:

> **An allowlist, exemption or suppression is an affirmative claim of inertness and carries
> the burden of establishment.** No entry may be added to any allowlist without a recorded
> disposition establishing that it never affected a committed number, or naming the numbers
> it did affect.

Strictly additive. Bars byte-identical across eight amendments. Identity moved from
`c56a57b82bc3e36e`. Move the pin **and run the suite before committing**, per the failure you
owned last node.

---

## SECTION C — THE AUDIT. NO RENDERS.

For every committed number computed through `_effect` or any of its copies:

1. Recover the **denominator value at computation time**. If denominators were not retained,
   recompute them from retained frames — the frames are the authority and this is why they
   were kept.
2. Classify each computation `FIRED` / `NEAR_FIRING` / `SAFE`, where `NEAR_FIRING` means the
   denominator sat within a declared factor of the guard threshold. **Declare that factor
   before computing anything**, and justify it — a near-firing denominator means the
   computation was one seed away from returning a fallback, which is a fragility finding even
   where nothing fired.
3. Report by consumer, not by site: how many clearing comparisons, how many floor and
   seed-only computations, how many census rank entries, in each class.
4. Disposition all 62 allowlist entries per A27.

Prioritise the floor and seed-only computations. They are the direction that manufactures
PASSes and they gate everything else.

---

## SECTION D — PRE-COMMITTED CONSEQUENCES. WRITTEN BEFORE SECTION C RUNS.

- **Fired in a clearing comparison** → the reading is not a measurement of the subject. Any
  FAIL resting on it is not a measured FAIL. Under 1c this is an improvement, so it is
  **held**, not committed, and placed with me.
- **Fired in a floor or seed-only computation** → that floor is not a measurement. Eligibility
  derived from it suspends, `required_clearing_effect` derived from it suspends, and every
  clearing measured against it suspends. Degradation: commits immediately.
- **Fired in a census rank vector** → that R5 reading is not a measurement; the independence
  verdicts resting on it suspend. Degradation: commits immediately.
- **Nothing fired anywhere** → say so plainly. That is a real result, it hardens the
  establishment table considerably, and it is the outcome the maximum-over-15-pairings
  argument predicts for the floors.
- **`NEAR_FIRING` found without `FIRED`** → no verdict moves, and the fragility is recorded
  with the named computations, because a statistic one seed from a fallback is a statistic
  whose replicate spread means something different than assumed.

---

## SECTION E — MANIFEST GATING

The 102-render manifest does not start until Section C closes. If any floor computation fired,
the eligibility set changes, which changes which axes need ensembles, which changes the
manifest. Re-plan it after the audit rather than mid-queue.

If Section C comes back entirely `SAFE`, the manifest stands as planned at 102 renders with
its per-member resumable boundary, and it is the next node.

---

## WHAT THIS NODE MAY NOT DO

Move a bar. Repair a fallback site — dispositioning is not repairing, and repair is its own
declared node with void lists. Commit an improvement. Render anything. Touch the frozen M5
instrument. Read, echo or commit `.env`.

## BOUNDARY REPORT

The amendment and both identities, with the pin moved and the suite run before the commit.
The declared `NEAR_FIRING` factor and its justification, stated before the results. The audit
by consumer class. All 62 dispositions. What suspended, what is held, and whether anything
fired at all. The re-planned manifest or confirmation that 102 stands. Failures owned. Then,
separately, the one thing you are least confident is correct, as a question.
