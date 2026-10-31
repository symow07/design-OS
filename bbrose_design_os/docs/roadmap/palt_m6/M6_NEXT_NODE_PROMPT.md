# Prompt for Claude Code — M6 instrument provenance repair, then the satin ruling

Paste the block below into Claude Code at the repo root.

---

You are continuing BBROSE Design OS at HEAD `c375264`, inside PALT-M6.

Before anything else: **do not execute `M6-SATIN-STRUCTURE-CORRECTION` yet.** It is
the committed next node and it is the wrong next move. Read this whole brief,
then start at Phase 0.

## Why the node order changes (and why this is not a scope change)

`SATIN_VS_CREAM` returned `FAIL_MATERIAL_MODEL`, and the declared response is to
raise satin's `micronormal_amplitude` one step and re-run all pairs. That is a
change to a **family definition** justified by a **measurement**. The project's
own rules make that conditional: rule 6 says diagnose before tuning, and rule 3
says when a metric fails you fix the instrument, never the bar — the family is
the subject-side analogue of the bar. So the material correction is legitimate
only once the instrument that produced the verdict has been proven honest.

At `67151ef` a read-only forensic pass found that it had not been. Those findings
are on disk and are reproducible without Blender:

- `bbrose_design_os/docs/roadmap/palt_m6/axis_instrument_defect_findings.json` — findings F1–F8, with measured numbers
- `bbrose_design_os/docs/roadmap/palt_m6/axis_instrument_forensics.py` — the read-only script that produced them; run it, do not import it into the instrument
- `bbrose_design_os/docs/roadmap/palt_m6/axis_instrument_forensics.json` — its output at `67151ef`
- `bbrose_design_os/apps/pipeline/services/palette_instrument_repair_protocol.py` — the declared repair, identity `1e198aed8d86ed9c`, families frozen, `bars_moved: []`
- `bbrose_design_os/docs/roadmap/palt_m6/open_defect_inventory.md` — the full register including the non-M6 items

**Those findings were recorded at `67151ef`, not at `c375264`.** Your first job is
to establish which of them are still true. The §§8–10 work rejected two candidate
axes with diagnosed formula defects, which plausibly closes F3 and part of F7.
Do not assume it closed the rest. Verify each finding at HEAD, and record every
one you find already closed as CLOSED with the commit that closed it — a finding
that quietly disappears is the same failure mode as a defect that quietly appears.

## The specific reason the satin verdict is not yet safe to act on

`CREAM` carries no grain at all. `POWDER_SATIN` carries `micronormal_amplitude`
0.10 at `microparticle_scale_mm` 0.21 — three pixels at 14.286 px/mm, which is
the smallest structure this rig claims to resolve, at the lowest amplitude any
family declares. That is precisely the signal an 8-bit display-encoded frame
quantises away.

So `FAIL_MATERIAL_MODEL` on satin-versus-cream has two live explanations, and the
current evidence cannot separate them:

1. satin's grain genuinely is indistinct from cream's smoothness — a real material
   finding, and the correction is warranted; or
2. satin's grain is present in the scene-linear render and destroyed by the
   measurement chain — in which case raising `micronormal_amplitude` would be
   moving the subject to satisfy a broken instrument, and would silently make
   satin coarser than it should be for the rest of the programme.

Phase 0 and Phase 1 exist to separate those two. Do not pick one in advance.

---

## Phase 0 — instrument provenance repair

Scope is `palette_instrument_repair_protocol.py` R1, R2 and R6 only. These three
are pure-instrument: none of them can change a family verdict by construction,
they can only change whether a verdict is trustworthy. R3 (withdraw the
autocorrelation axis) is likely already done at `c375264` — confirm and record.
R4 and R5 have verdict consequences and are deliberately held for Phase 2.

Re-run `axis_instrument_forensics.py` at HEAD first, and record the result, before
you change anything.

**F1 / R1 — measure from scene-linear.** `blender_scripts/material_characterization.py:268-274`
sets `color_depth = "16"` and then writes a file that is, on disk, 8-bit RGBA. The
comment above that block states plainly that 8 bits would crush event contrast
into quantisation noise, so the intent is unambiguous and the realization is
absent. Do not fix this by making the PNG genuinely 16-bit. The renderer already
writes a float EXR on every render; make every measurement read that, in
scene-linear, RGB only. Demote both PNGs to human-review artifacts that no
measurement may take as input.

Add `FRAME_PROVENANCE_ASSERTION`: the loader accepts only a floating-point array
with at least three channels, drops alpha explicitly, and **raises** on a `uint8`
array. The negative control is to hand it one of the existing 8-bit RGBA frames
in `docs/roadmap/palt_m6/texture_axes/` and assert that it raises. A guard that
cannot reject the artifact that caused the defect is not a guard.

**F2 — alpha contamination.** `palette_powder_texture_axes.py:79-81` does
`raw.astype(float).mean(axis=2)` on a 4-channel frame, so every axis is computed
from `(R+G+B+255)/4`. Measured consequence at `67151ef`: `GRAZING_BAND_CONTRAST`
on its own positive fixture reads 0.2683 as the instrument reads it, 0.1078 on RGB
only, 0.1252 on EXR — against a bar of 0.25. The only reading under which that
axis passed was the contaminated one. R1 removes this as a side effect; assert it
anyway, because the next reader to reach for `.mean(axis=2)` will be doing it
somewhere else.

**F6 / R2 — stimulus realization gate.** Nothing anywhere checks that the two
members of a fixture pair actually rendered differently. Renders are deterministic
and fixture pairs share a seed, so an unrealized parameter produces bit-identical
frames and every axis reports exactly 0.0 — which the study then records as "the
axis is blind." That is the false conclusion drawn at `927ab8a` and withdrawn at
`05d481c`, and `texture_axes_validation.json` still carries its fingerprint:
`low == high` to six decimal places on all three axes.

Every fixture pair, in every study, computes a frame-level difference over the
measured region **before** any axis is evaluated. Below the declared realization
floor of 0.002 of the low member's region mean, the pair reports
`STIMULUS_NOT_REALIZED` and **no relative effect is recorded at all**. Make
`detects: false` unreachable for an unrealized stimulus. The floor is a
realization floor, not a pass bar; it is never compared against 0.25. Negative
control: an identical-spec pair must report `STIMULUS_NOT_REALIZED`, not "no axis
detects."

**F7 / R6 — no silent fallbacks.** `lag_mm` stays 0.0 when variance is under the
numerical floor; `contrast` returns 0.0 when the region median is zero. A reader
cannot tell "measured zero" from "declined to measure." Every degenerate branch
raises. Test asserts the raise on a black region.

Phase 0 exit: all of these assertions exist, and each one's negative control is
recorded as having **failed correctly**. An assertion with no demonstrated failure
mode does not count.

## Phase 1 — re-establish the §§8–10 rulings on the repaired instrument

Families stay frozen. Nothing about satin changes in this phase.

Re-run, on scene-linear frames, with the identical declarations: the axis
sensitivity study; the `GRANULARITY_INDEX` admission including all four §7
controls; and all three diffuse pair rulings.

Then answer these explicitly in the record, one line each:

- Does `GRANULARITY_INDEX` still admit? Its positive-fixture effect was 0.456 as
  measured through the contaminated reader. On EXR at `67151ef` the same fixture
  measured 0.8641 versus 0.6318 as-instrument — the magnitudes move materially, so
  re-derive the number rather than carrying it forward.
- Does the exposure-only control still read ~0.0008? Mean-normalisation is
  scale-invariant, but the alpha channel added a *constant*, which is not, so that
  control was passing under conditions that should have perturbed it. If it still
  reads near zero on clean frames, say so — that strengthens the axis.
- Do `MATTE_VS_SATIN` and `PRESSED_VS_MATTE` still PASS, on which axes, at what
  effects?
- **Does `SATIN_VS_CREAM` still return `FAIL_MATERIAL_MODEL`?** This is the
  question the whole reordering exists to answer.

If any verdict changes, supersede the prior record in place with the reason
recorded. Do not delete it.

## Phase 2 — axis eligibility and measured independence (R4, R5)

These have verdict consequences, which is why they come after the instrument is
clean and before any family is touched.

**F4 / R4 — per-axis noise floors.** `EDGE_HIGHLIGHT_RESPONSE` cleared the 25% bar
on a seed-only negative control at 0.27991 — two `POWDER_MATTE` specs differing
only in random seed. It was then counted as a clearing axis in `MATTE_VS_SATIN` at
0.3604, which is 1.29× its own noise. The control never flagged this because a
control's success criterion is the *pair* verdict, so a single axis firing on
noise is invisible to it; `controls_misbehaved` was recorded as `[]`.

Measure a seed-only noise floor per axis from a same-family, same-parameter,
seed-varied ensemble. An axis whose floor is at or above 0.25 is **ineligible to
carry a pair**. A clearing result must exceed its own floor by the declared
margin of 2.0. This does not raise the pass bar — the bar stays 0.25 for every
axis; it adds an eligibility precondition on the instrument, in the same spirit as
enlarging the light source rather than lowering a threshold.

Then re-adjudicate both current PASSes with EDGE's floor applied. `MATTE_VS_SATIN`
now rests on SHEEN + EDGE + GRANULARITY; if EDGE is ineligible it must still hold
on SHEEN + GRANULARITY, and you must show that rather than assume it.
`PRESSED_VS_MATTE` has four axes and should survive. Record whichever way it goes.

**F5 / R5 — independence becomes measured.** `axes_from` in
`palette_characterization_rig.py:266-281` reads the identical scalar
`highlight_fwhm_fraction` four times, differing only by region:
`HIGHLIGHT_FWHM` (QUARTER_CYLINDER), `GRAZING_RESPONSE` (GRAZING),
`SHEEN_REGION_RESPONSE` (SHALLOW_CURVE), `EDGE_HIGHLIGHT_RESPONSE` (BEVEL). The §6
correction already caught this once — five axes previously read peak/median — and
the fix changed *which* scalar was shared rather than removing the sharing.
`PASS_LAW.required_independent_axes` is 2, and independence is currently a word in
a docstring.

Compute absolute Spearman rank correlation between every axis pair across the
family census. Two axes above the declared ceiling of 0.80 may not both count
toward the same pair's two-axis requirement. This does not change the law; it
makes the word "independent" in the law checkable. Note that `MATTE_VS_SATIN` on
SHEEN + GRANULARITY would be two axes on two different instruments, which is the
strongest form of independence available here — but measure it, do not argue it.

## Phase 3 — only now, the satin question

With a clean instrument, eligible axes and measured independence, re-read
`SATIN_VS_CREAM`.

If it still fails, the material finding is real and `M6-SATIN-STRUCTURE-CORRECTION`
proceeds exactly as declared: one controlled step up in `micronormal_amplitude`,
still well below matte, then all M6 pairs re-run because no PASS is inherited
across a shader revision.

If it now passes, the correction is withdrawn, the `FAIL_MATERIAL_MODEL` verdict
is superseded in place with the instrument defect named as its cause, and satin's
declared structure is left alone. Record which of the two happened and why. Either
outcome is a result; only guessing between them is not.

## Phase 4 — resume the declared chain

Before the flake rig, re-measure the `GLITTER_PARTICLE_RIG` census from the EXR.
`palette_powder_rigs.py:344` reads the same `png16` the rest of this brief is
about, and the 87-event PASS at `27ded17` therefore rests on the exact condition
its own justifying comment says would invalidate it. Confirm or withdraw it. It is
in question, not overturned.

Then the declared chain, unchanged: flake rig → metallic-vs-glitter cross-check →
BAKED dome geometry with CLOSED clearance → marbling rig → full negative-control
matrix and independence audit → ES3083/FB3093 products and observability →
workflow trace → five boards → 21-condition gate with the full canonical suite →
M7.

## Independent of M6 — do these in parallel, they block nothing

`docs/roadmap/progress_tracker.json` records `PALT-M2` through `PALT-M7` as
`NOT_STARTED` and titles `PALT-M6` "artwork + shade system + .AI export." On disk,
M1–M3 are owner-accepted, M4 was owner-rejected and repaired through M4B/M4C, M5
closed 19/19, and M6 is the powder engine. The file was last written 2026-08-05
and has been contradicted by every commit since.

This matters beyond staleness, because `manage.py roadmap_status` is the project's
sole legitimate source of a progress percentage and it computes that percentage
from this file. Reconcile it — and add the invariant that matters more than the
reconciliation: **the tracker may not report `NOT_STARTED` for a milestone that
has a closure record on disk.** That is checkable, and it is what stops this
recurring.

`apps/dielines/models.py` `TemplateType` declares four choices;
`apps/dielines/registry.py` registers six `template_id`s —
`ecma_a20_20_01_01_ste_carton` and `reference_opposed_tuck_carton` have no enum
member. Add the assertion that the two lists agree. Do the same for the three
Design Target lists that a new target breaks. These are the same defect class as
everything above, wearing different clothes.

Leave `README.md`, `PROJECT_DOCUMENTATION.md`, `EXECUTION_STATUS.md` and
`AUDIT_REPORT.md` until M6 closes, so they get rewritten once and correctly. Two
claims in them are affirmatively false rather than merely stale and should be
noted now: that the IRE M3 backbone "sits unused" — it is wired live into
`reconstruct_container` via `m3_backbone.build_container_backbone`, commit
`d92c370` — and the M6 numbering above.

## Rules of engagement

Do not move `PASS_LAW` (2 independent axes at ≥ 25%), the validity window
`[0.35, 0.92]`, `max_clipped_samples: 0`, `SENSITIVITY_BAR`, `EFFECT_BAR`, or
protocol identity `087c7f64317910fb`. Families stay frozen through Phases 0–2; the
only family change permitted anywhere in this brief is the satin step in Phase 3,
and only if Phase 3's re-read still calls for it.

Every phase writes an evidence record naming what it measured and what it refused
to conclude. Superseded records are superseded in place, never deleted. The
canonical suite result is written to an external record with the git SHA pinned
inside it — the suite does not verify itself. `owner_approved` stays `false`
throughout; nothing here approves itself, and `manufacturing_authority` remains
`NOT_ESTABLISHED`.

If a phase produces an honest FAIL, commit the FAIL. Two M6 verdicts have already
been withdrawn because a measurement chain was trusted past what it could support;
a third would be a pattern, not an accident.

Do not touch the standing external blockers — `SUPPLIER_DATA`,
`MATERIALS_LIBRARY_ABSENT`, `ES3083_DIMENSIONS_UNREADABLE`,
`VQ1_HUMAN_STRUCTURAL_REVIEW`. They need the owner or files that are not in this
working copy. No plan should route around them.
