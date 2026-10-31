# M6 — CONTROL COVERAGE

Follows `M6-MARBLING-INSTRUMENT-REPAIR` (`30132e4` → `c5c3420`), law at `950499d757b8d368`.
Owner authorization: transmission authorizes Section A and the seventh amendment. Object
rather than execute if any of it is wrong.

---

## SECTION A — RULINGS

### A21. Shade-symmetric controls are required, and this is not a control chosen after a
number

You asked whether requiring a candidate's positive control to pass at both provisional shade
assignments — after seeing C3's asymmetry — constitutes choosing the control after the
number.

Ruling: **it does not, because it is not a new requirement.** It is the standing prohibition
on reading a null from an instrument not validated at the condition of the reading, applied
where it had not been applied.

C3 reads 0.0638 at the warm pair. Its positive control was established at the cool pair.
Nothing in the record distinguishes *the warm marble has low hue dispersion* from *C3 is
blind at warm*. That is the identical shape as the sub-pixel zero read as a measurement, the
`RAKING_SHADOW_FRACTION` silent zero, and the fallback you caught in your own tooling this
node: a null reading from an instrument that could not have produced a non-null one under
those conditions. Nothing about that prohibition was invented today.

The asymmetry between sensitivity and specificity, hashed below, is what makes it operable:

> **A clearing reading is self-validating for sensitivity** at its own condition — an
> instrument that reports a large effect there is demonstrably not blind there. **It is not
> self-validating for specificity.** The negative control must hold at every condition where
> the axis is counted, because a large reading may be the instrument responding to seed or
> placement at that condition even where it does not at another.
>
> **A null or non-clearing reading is not self-validating for anything.** It may be counted
> as a measurement of the subject only where the positive control passes at that same
> condition. Otherwise it is `INSTRUMENT_NOT_VALIDATED_AT_CONDITION` and carries nothing in
> either direction — it is not evidence the subject is null, and it is not evidence the
> instrument is blind.

**Note what this costs, because it is the reason the ruling is safe to make.** It does not
threaten C3, whose branch ends in FAIL either way — if the warm positive control passes,
0.0638 is a real non-clearing reading; if it fails, C3 is blind at warm and cannot count
there. It threatens **C2**, your one qualifying axis, which needs a warm-shade negative
control it has never had. If that control fails, `SOLID_VS_MARBLED` has zero qualifying axes
rather than one. A correction that cannot improve the verdict and can unmake the surviving
axis is not one anybody reached for, and that is the evidence it is not motivated.

Honest qualifier set as of now: **C2 pending its warm negative control; C3 pending its warm
positive control.** Neither is qualified today. The FAIL stands regardless.

### A22. The silent-fallback class returned a fourth time. The guard did not generalize.

Four appearances: `grid_correlation`'s degenerate-path 0.0, `RAKING_SHADOW_FRACTION`'s silent
zero, the constant-vector `argsort(argsort(·))`, and now mask-mode consumed as an index list
falling through to whole-frame statistics. The third-appearance guard was scoped to rank
correlations **in the codebase**. This one lived in analysis tooling, outside its reach, and
was caught by domain reasoning — the failure pattern contradicting post-C6 chroma physics —
rather than by any guard. Catching it that way was good work and it is not a system.

The class, named properly: **an operation that, given malformed, absent or unexpected input,
silently produces a plausible in-range result instead of raising.**

Required response, class-level rather than instance-level:

1. Extend the guard's scope from rank correlations to **every measurement and analysis path,
   including ad-hoc analysis scripts and one-off tooling**. Tooling that produces a number
   which reaches a record is measurement code, whatever directory it lives in.
2. Enforce it with a test that scans measurement and analysis modules for the fallback
   shapes: default-on-lookup-failure, bare or over-broad `except`, silent type coercion,
   and index/mask conflation of the kind that fired here. The test fails the suite on a new
   occurrence.
3. Sweep the existing analysis tooling for other instances and report the count. If it
   returns zero, say so — that is a result.
4. Record in the defect register that the third-appearance guard was scoped too narrowly and
   that a scope check is now part of declaring any structural guard: *what is the class, and
   does the guard cover all of it, or only where it was found?*

### A23. Declare the identity-zero constant rather than exempt it

The `distortion` default is relied on at seven sites and was recorded as a judged exemption
because its value is the identity element. The judgment is sound and the exemption is still
the wrong disposition: an undeclared constant whose value happens to be inert today moves
seven sites silently if anyone ever changes it, and "it is currently zero" is a fact about
the value, not about the contract.

Declare it with value 0. It costs nothing, it removes a judged exemption from the record,
and it puts the seven sites under the same contract discipline as everything else. Judged
exemptions should be rare enough to be memorable; this one does not need to be one.

### A24. My numbering error, and your correction

`1k` was already occupied by the fifth amendment; you hashed the instrument-correction rule
as `instrument_correction_1n` and recorded the collision rather than absorbing it. My error,
your handling is right, and the label stands as you set it. I will refer to it as `1n`.

---

## SECTION B — SEVENTH AMENDMENT: CONTROL COVERAGE

Hash A21's sensitivity/specificity asymmetry and the `INSTRUMENT_NOT_VALIDATED_AT_CONDITION`
status. Strictly additive. Bars byte-identical across seven amendments. Identity moved from
`950499d757b8d368`; chain recorded. Check A22's guard extension is expressible as law rather
than only as a test, and hash whichever part belongs in the law.

---

## SECTION C — DISCHARGE THE MARBLING CONTROLS

From retained frames wherever possible; report what cannot be computed without rendering
before rendering anything.

1. **C2 warm-shade negative control** — must fail to distinguish two warm marbles of
   identical material at different seeds. Declare the reading before measuring: what value
   constitutes failure of the control, in advance.
2. **C3 warm-shade positive control** — must distinguish a warm marble from a material known
   to differ chromatically, live fixture.
3. Re-rule `SOLID_VS_MARBLED` with the qualifier set that survives. Every branch ends in
   FAIL on the current evidence; commit the FAIL with the qualifier count stated, since one
   qualifying axis and zero qualifying axes are materially different records of the same
   verdict.
4. If C2 fails its warm negative control, record plainly that the marbling family is
   currently distinguishable on **no** commissioned axis, and that this is a fact about the
   rig suite.

---

## SECTION D — RETROACTIVE CONTROL-COVERAGE SWEEP

A21 is not marbling-specific, and the same structure exists elsewhere. The clearest instance:
the axis noise floors were measured on a **POWDER_MATTE** ensemble (seeds 40, 81–84, 99) and
used for eligibility and floor comparison across **every** family. That is an instrument
property established at one condition and applied at others — the same shape A21 rules on.

A11's transfer method already noticed a version of this and rejected `SATIN_VS_CREAM` and
`METALLIC_VS_GLITTER` for lacking a measured member family. Extend that machinery from
spreads to controls.

Scope it and do not let it sprawl: for every axis reading currently counted toward any
verdict, one row — the axis, the condition of the reading, the condition at which its
negative control (floor) was established, the condition at which its positive control was
established, and COVERED / `INSTRUMENT_NOT_VALIDATED_AT_CONDITION`. Apply the burden rule
from 1j to the result: affirmative claims suspend, refusals and exclusions stand.

Do not measure anything to fill the gaps in this node. Producing the table is the work; the
measurements belong to Section E's manifest.

---

## SECTION E — REPLAN THE MEASUREMENT MANIFEST BEFORE ANY OF IT RENDERS

Section D will likely require per-family instrument properties that the ruled order did not
anticipate. That changes the render manifest for the measurement nodes, so the manifest is
replanned now rather than discovered mid-render.

Plan together, as one manifest, without executing any of them:
`M6-DECLARED-ENSEMBLE-SPREADS`, `M6-CENSUS-REPLICATE`, the control-coverage gaps from
Section D, and — checked for overlap only — `M6-FLAKE-INDEPENDENCE-RE-ADJUDICATION`.

Report: total renders if each node runs independently; total if planned as one manifest;
the shared frames that produce the difference; and the order that lets the queue be stopped
and resumed at a boundary without wasting work. Then stop. The manifest is the deliverable,
not its execution.

---

## WHAT THIS NODE MAY NOT DO

Move a bar. Relax a tolerance. Re-draft a frozen declaration. Rescue a verdict. Execute any
measurement node. Fill Section D's gaps with new measurements. Touch the frozen M5
instrument. Read, echo or commit `.env`.

## BOUNDARY REPORT

The amendment and both identities. C2 and C3's warm controls with their pre-declared
readings, and the re-ruled `SOLID_VS_MARBLED` with its qualifier count. The A22 guard
extension, the tooling sweep count, and the register entry about scoping guards to classes
rather than to instances. A23 done. The Section D table. The Section E manifest with the
saving from planning them together. Failures owned. Then, separately, the one thing you are
least confident is correct, as a question.
