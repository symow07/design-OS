# Phase 2A-9C — Multi-Archetype Qualification Framework (PROPOSAL)

**Status: planning only — not implemented.** Prepared per the 2A-9B
acceptance. Implementation starts only after this scope is approved, one
archetype slice at a time, each ending at a review stop.

## Principle

Qualification is never inherited. `reference_opposed_tuck_carton/0.1`
holding TECHNICALLY_QUALIFIED_DOMAIN says nothing about any other carton
structure. Each candidate gets its own parameter contract, its own derived
domain, its own invariants, sweep, boundary fixtures, folded simulation,
physical-test matrix and its own explicit unsupported regions.
`tuck_top_auto_bottom_carton` stays excluded — its closure mechanics carry
`MEASURED_REFERENCE_REQUIRED` and no qualification can substitute for a
measured production reference.

## Shared framework work (slice 0 — prerequisite)

The 2A-9B framework is adapter-based but two pieces are still bound to the
opposing-tuck archetype and must be generalized first, without touching
any locked geometry:

1. **Folded-closure model per closure type.** `folded_diagnostic` and the
   folded collision checks assume opposing tucks with entry slits. The
   legacy engine archetypes use a **stadium friction slit** (DECISION-010/
   017) and **2t shoulder lock notches** (DECISION-015) instead of
   entry-slit ears, and hang the two tucks on back/front. The adapter
   gains a closure descriptor (tuck panels + lock mechanism + slit model)
   that both the simulation and the invariants read.
2. **Capability-driven invariants.** Slit counts, ear/slit alignment and
   crease-shortening checks derive from the registry's declared
   capabilities instead of hard-coded expectations.
3. **Endpoint registry.** `/api/dielines/qualify_dimensions/` looks up an
   adapter registry instead of the single hard-coded template, and the
   dimension-gate UI keys off "has an adapter" rather than a template
   name.
4. **Report command.** The 2A-9B report generation (matrix, sweep, domain,
   renders) becomes a management command so each archetype's committed
   report regenerates identically.

Estimated effort: **~0.5 review slice.** Risk: low (refactor with the
opposing-tuck qualification suite as the non-regression net — its seed,
matrix and hashes must reproduce byte-identically).

## Slice 1 — straight_tuck_end_carton/1.1

Why first: the only production-eligible legacy archetype, measured
28×28×120 reference, most historically used.

- Contract: DECISION-016 ratio constants (tuck_h = W×1.227,
  dust = D×0.631, slit = W×0.327, inset = W×0.227, curve = W×0.218), lock
  notches 2t, friction-slit stadium dimensions, glue corner factors —
  all published as TEMPLATE_CONSTANTs; thickness compensation is opt-in
  and must be qualified in BOTH modes (t = 0 legacy reproduction and
  compensated).
- Domain derivation to establish (not guess): tuck-vs-dust clearance
  (already clamped — the clamp boundary becomes a domain edge, since a
  clamped dust flap is a formula change in disguise), slit web guard
  floor, D ≤ 2.5·W, H > W/D, ratio-driven tuck height vs body height
  (W×1.227 can exceed H for wide-short cartons), lock-notch feasibility
  vs t.
- Expected outcome: genuine unsupported regions in the raw space. Any
  invariant failure inside the intended domain is NOT silently fixed —
  it is published as an unsupported region, or fixed as version **1.2**
  with 1.1 kept for historical reproduction.
- Estimated effort: **~1 review slice.** Risk: medium — the ratio
  formulas were only ever exercised near the measured reference; the
  sweep may surface real geometric corner cases.

## Slice 2 — skynte_foundation_tuck_carton/1.0

Why second: customer-derived, in active use, spec-driven module
(side_seam.py) whose parameters are already explicit
(SideSeamTuckSpec: tuck lip 16, entry slits 5, dust factor 0.631,
shoulder factors).

- Contract: the SideSeamTuckSpec fields map almost 1:1 onto
  TEMPLATE_CONSTANTs; panel order glue | side | main | side | main needs
  the adapter's attachment model (tucks on the two MAIN panels at
  positions 3 and 5).
- Domain: D-based tuck heights (tuck = D + lip) change the binding
  constraints — the folded dust/tuck interactions derive differently
  from the opposing-tuck case.
- Estimated effort: **~0.75 review slice.** Risk: low-medium.

## Slice 3 — reverse_tuck_end_carton/1.1

Why last: provisional (no measured reference), least used; shares the
engine formulas with STE 1.1, but qualification is still fully
independent — its mirrored closure changes the folded model and its
provisional status must be visible in every report
(TECHNICALLY_QUALIFIED_DOMAIN would still not make it production-ready;
its registry `provisional` flag and confirmation gates stay untouched).

- Estimated effort: **~0.5 review slice** (after STE's adapter exists).

## Ordering summary

| Order | Slice | Effort | Stop |
|---|---|---|---|
| 0 | shared framework generalization | ~0.5 | review: opposing-tuck reports reproduce byte-identically |
| 1 | straight_tuck_end_carton/1.1 | ~1.0 | review: domain + matrix + unsupported regions |
| 2 | skynte_foundation_tuck_carton/1.0 | ~0.75 | review |
| 3 | reverse_tuck_end_carton/1.1 | ~0.5 | review |

Total ≈ 2.75 review slices. Each slice: contract → derived domain →
fail-closed wiring → invariants → seeded sweep + boundary fixtures →
folded simulation → committed reports → physical-test matrix → tests →
stop. No provider calls anywhere; Gate 2 untouched; no artwork work.

## Explicitly out of scope

- `tuck_top_auto_bottom_carton` (any version) — MEASURED_REFERENCE_REQUIRED.
- Promoting any archetype past TECHNICALLY_QUALIFIED_DOMAIN.
- Changing locked geometry (STE 1.0/1.1 byte-stability guards stay).
- Task-50 artwork remap (blocked on its physical result).
