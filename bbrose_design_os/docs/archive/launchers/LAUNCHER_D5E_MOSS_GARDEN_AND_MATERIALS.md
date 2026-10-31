# LAUNCHER — D5e, MOSS GARDEN AND THE MATERIALS LIBRARY

Follows `829c598`. Two acts. The first is a diagnostic, not a re-spec. The
second closes the cheapest of the four standing blockers, and closes it by
correcting a false statement rather than by finding anything.

---

## WHAT I CHECKED BEFORE WRITING THIS

Four things, and three of them change what the brief has to say.

### 1. The D5d Moss Garden measurement used the wrong instrument

`829c598` reported Moss Garden's marbling as *"relative range 0.284 against
Sage Stem's 0.341"* — an ad-hoc luminance range, computed over the composed
swatch.

But this programme already owns a commissioned instrument for exactly this
question. `apps/pipeline/services/palette_marbling_rig.py` declares two axes,
`palette_marbling_rig.py:64–67`:

- **`MARBLE_CHROMA_SPAN`** — p95 − p5 of `(R − B) / (R + G + B + eps)` over the
  planar region. The amplitude of colour separation between marble components.
- **`MARBLE_CHROMA_COHERENCE`** — the fraction of chroma variance captured by
  an 8×8 block-mean downsample. Spatial regions score high, per-pixel speckle
  scores low.

with commissioned floors from a six-seed ensemble (`FLOOR_SEEDS = (500…505)`),
a `PASS_BAR` of 0.25, a `SEPARATION_MARGIN` of 2.0, and a required
`SOLID_VS_MARBLED` negative control against a matched `POWDER_MATTE` render of
the same shade.

A luminance range is not either of those axes. Marbling is a *chromatic-spatial*
property — the rig's own docstring says the illumination is deliberately boring
because "the question is chromatic-spatial." So the number we have does not
answer the question we asked, and Moss Garden has never actually been measured
on the instrument built to measure it.

### 2. The mechanism is not a mystery — the coefficients are recorded

`palette_marbling_rig.py:72–76`, `DERIVED_COEFFICIENTS`:

> *"component colours derived by x0.55 (darker) and x1.35+0.05 (lighter) —
> undeclared builder coefficients, the source of every chroma number below"*

Both terms are base-dependent, and the additive `+0.05` is the interesting one.
It is added to all three channels equally, so it is a **desaturating offset
whose weight scales inversely with the base value.** On a bright base it is a
rounding error. On Moss Garden's scene-linear base — roughly 0.064 / 0.098 /
0.049 — it is comparable to the base itself, so the "lighter" marble component
arrives close to neutral grey while the darker one keeps its hue.

That predicts something specific and testable, and it is not what I assumed
when I told the owner the marbling was being crushed by darkness. It predicts
the *chroma span* may be fine or even inflated while the **coherence** and the
visible result collapse, because one component has stopped being olive. The
brief must test the prediction rather than assume my version of it.

### 3. My "eight of twelve below the window" repeat does not reconcile

`SUBJECT_WINDOW = (0.35, 0.92)`, `palette_powder_texture_axes.py:534`, with a
hard refusal at line 661 when `scene_linear_peak < 0.35`.

`829c598` reported eight of twelve owner shades below the floor. Taking peak
channel through `srgb_to_linear` I count **five** — Sage Stem 0.231, Old Rose
0.266, Thorn 0.109, Moss Garden 0.098, Midnight Bloom 0.068 — with Copper Leaf
at 0.392 marginally inside. Eight and five are different findings and one of us
is using a different definition of "peak." Mine may well be the wrong one. It
needs stating, not averaging.

**And the part that matters regardless of which count is right:** these shades
moved *out* of the window because of `beb1fe5`. Before the transform they sat
at their sRGB values, where Moss Garden's peak was 0.345 — just under the
floor. After it they sit at linear, where it is 0.098 — nowhere near. The
colour fix was correct and it is also what pushed the palette outside the
instrument's declared operating range. Both of those are true at once and the
record should say so.

### 4. `MATERIALS_LIBRARY_ABSENT` is not true

The record, `docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json:272`
and `:343–345`:

> `"materials_library": "absent from this working copy; native .ai sources unopenable here"`
> `{"id": "MATERIALS_LIBRARY_ABSENT", "kind": "EXTERNAL", "detail": "native .ai sources not in this working copy"}`

In the working copy right now: `materials/`, **28 GB**, containing **226 `.ai`**,
536 `.eps`, 3,686 `.ttf`, 1,116 `.otf`, 87 `.psd`. It is gitignored on purpose —
`.gitignore:54`, described there as *"Design Intelligence source library (28GB
of historical .ai, assets, fonts). READ-ONLY source material — never committed,
never modified. See tools/dip0/."*

It is not merely present. It has already been mined. `tools/dip0/` walks,
classifies and audits it; `var/design_intelligence/audits/` holds the inventory
and per-file analyses. And the decisive one:

```
materials/historical AI production designs/ES3083吸塑 展盒刀线.ai
var/design_intelligence/audits/dip0b/unit_analysis/ES3083吸塑 展盒刀线-p0.units_b4.json
```

That analysis carries `artbox_pt`, `dieline_outcome: LIKELY_DIELINE_STRUCTURE`,
and `separation_inks: ["PANTONE 621 C", "PANTONE 627 C"]` — the two Pantone
tokens D5 has been holding symbolically. **`ES3083_DIMENSION_FINDINGS.md` at
this repo's root already measured that file.** So a blocker asserting the
library is absent has been false since before the document that disproves it
was written, and nobody noticed because nothing checks a blocker's premise.

That is an A564 defect in the roadmap state — an absence claim, carried as an
`EXTERNAL` blocker on M7, that no search extent would have survived.

The honest resolution is not "close it." It is: state what is actually present
with its extent, then state what — if anything — is genuinely missing, and let
the blocker be either withdrawn or re-scoped to the true residue. It may turn
out the true residue is nothing, in which case the count of standing blockers
drops without a single file being obtained.

---

## THE PROMPT

```
GOAL — two acts. ACT A is a diagnostic render that decides whether Moss
Garden's marbling can be made to read. ACT B resolves a blocker that is
factually false. They are independent: if ACT A cannot run, say so early and
still do ACT B in full.

CONTEXT
  apps/pipeline/services/palette_marbling_rig.py        (read it FIRST)
  apps/pipeline/services/palette_powder_texture_axes.py (SUBJECT_WINDOW:534)
  apps/pipeline/services/palette_powder_engine.py       (es3083_owner_shade_set)
  docs/roadmap/palt_m6/owner_swatches/                  (the 829c598 output)
  docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json
  docs/roadmap/palt_m6/open_defect_inventory.md
  .gitignore:54, tools/dip0/, var/design_intelligence/audits/
  ES3083_DIMENSION_FINDINGS.md

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

=============================== ACT A ===============================

STEP A1 — MEASURE MOSS GARDEN ON THE RIGHT INSTRUMENT

  The 829c598 finding ("relative range 0.284 vs Sage Stem 0.341") is a
  luminance statistic. Marbling is chromatic-spatial and this programme owns
  a commissioned instrument for it: MARBLE_CHROMA_SPAN and
  MARBLE_CHROMA_COHERENCE, with floors, PASS_BAR 0.25, SEPARATION_MARGIN 2.0,
  and a required SOLID_VS_MARBLED control.

  Measure Moss Garden as authored (#48583F, seed = pan 11, transform applied)
  on BOTH declared axes, against a POWDER_MATTE control of the same shade and
  the same seed. Report the effect sizes and whether each axis counts, using
  the rig's own adjudicate() semantics.

  If the rig refuses because Moss Garden's scene-linear peak is below
  SUBJECT_WINDOW[0], THAT IS THE ANSWER TO STEP A2 AND YOU SHOULD SAY SO
  RATHER THAN WORKING AROUND IT. Do not lower the window. Do not add a
  bypass. A refusal is a result and it is the most informative one available.

STEP A2 — THE LIGHTNESS LADDER, AS A CONTROLLED EXPERIMENT

  Question: is Moss Garden's marbling invisible because of the restraint note,
  or because of its own darkness?

  Render a ladder. Hold hue and relative chroma fixed, vary lightness only.
  Same seed, same rig, same lighting, same exposure, same camera, MARBLED
  family throughout. At minimum:

    - Moss Garden as authored
    - the same hue at scene-linear peak 0.35   (the window floor exactly)
    - the same hue at scene-linear peak 0.53   (where the nine families were
      proven — confirm that number from the record rather than trusting it
      from this brief)
    - the rig's own commissioning shade prov_dark_warm_sienna as a positive
      control, so the ladder is anchored to a value known to produce structure

  State exactly how you constructed the lighter variants and in which space,
  because "same hue, more lightness" is ambiguous and the method is part of
  the result.

  Then plot both chroma axes against scene-linear peak across the ladder and
  answer one question in one sentence: does marbling structure appear as
  luminance rises, and if so, at what value does it cross PASS_BAR?

  MY HYPOTHESIS, WHICH YOU SHOULD TRY TO FALSIFY. The builder derives marble
  components by x0.55 and x1.35+0.05 (DERIVED_COEFFICIENTS, line 72). The
  +0.05 is added to all channels equally, so it desaturates, and its weight
  relative to the base grows as the base darkens. On Moss Garden's linear base
  (~0.064/0.098/0.049) it is comparable to the base itself, so the "lighter"
  marble component should arrive close to neutral while the darker keeps its
  hue. That predicts COHERENCE and visible olive-vs-gold structure collapse
  while SPAN may be unaffected or even inflated. If the measurements say
  otherwise, the measurements win and I want to be told plainly.

  THIS IS A DIAGNOSTIC. Do not change Moss Garden's recorded hex, do not
  change its family, do not touch es3083_owner_shade_set(), and do not amend
  the shade authority record. The owner decides what to do with the answer.

STEP A3 — OPEN THE SUBJECT_WINDOW DEFECT

  SUBJECT_WINDOW = (0.35, 0.92), palette_powder_texture_axes.py:534, refused
  at :661 when scene_linear_peak < 0.35. 829c598 reported eight of twelve
  owner shades below the floor.

  I count five by taking the peak channel through srgb_to_linear — Sage Stem
  0.231, Old Rose 0.266, Thorn 0.109, Moss Garden 0.098, Midnight Bloom 0.068,
  with Copper Leaf marginal at 0.392. Eight and five are different findings.
  State the definition of "peak" you used, recompute both ways, and say which
  is right. If mine is wrong, say so directly.

  Then open a defect in open_defect_inventory.md carrying:

    - the finding: the rig's validated measurement window does not cover the
      depth range of the actual product palette, and the affected shades are
      refused rather than measured badly, which is the instrument behaving
      correctly
    - the count, with the peak definition stated
    - the causal note, which is the uncomfortable part: these shades moved
      out of the window because of beb1fe5. Before the transform Moss Garden
      sat at 0.345, just under the floor; after it, at 0.098. The colour fix
      was correct AND it is what put the palette outside the instrument's
      range. Record both, not one.
    - the compounding relationship to D7: the M6 family proofs were
      established inside a window that two-thirds of the shipping palette
      sits below, and per D7 the corpus that established them cannot be
      re-derived. State what those two facts jointly permit the M6 corpus to
      be cited FOR, and what they forbid it being cited for.
    - status OPEN, NOT scheduled, because M6 is parked
    - what closing it would require, in one sentence

  Do not widen SUBJECT_WINDOW. Do not re-commission any rig. Opening it is
  the whole task.

=============================== ACT B ===============================

STEP B1 — ESTABLISH WHAT IS ACTUALLY THERE, WITH EXTENT

  palette_roadmap_continuation_state.json:272 says the materials library is
  "absent from this working copy; native .ai sources unopenable here", and
  :343-345 carries MATERIALS_LIBRARY_ABSENT as an EXTERNAL blocker on M7.

  Both halves of that appear to be false. Verify before correcting anything —
  do not take this brief's word for it:

    a. Does materials/ exist in the working copy, and what does it contain?
       Give counts by extension and total size. Note it is gitignored at
       .gitignore:54 as a deliberate READ-ONLY source library, which is a
       different thing from absent.
    b. Is materials/historical AI production designs/ES3083吸塑 展盒刀线.ai
       present, and did ES3083_DIMENSION_FINDINGS.md measure it?
    c. What has tools/dip0 already extracted into
       var/design_intelligence/audits/ — inventory, per-file unit analysis,
       spot inks? Confirm the ES3083 units_b4 analysis carries PANTONE 621 C
       and 627 C as separation inks.
    d. Is "unopenable here" true? You have opened .ai files in this repository
       this month. Say what is and is not openable, and by what path.

  State your search extent per A564 for every claim, including the negative
  ones.

STEP B2 — SAY WHAT, IF ANYTHING, IS GENUINELY MISSING

  This is the part that decides the blocker's fate, and it is the part where
  it would be easy to declare victory too fast.

  A materials library being present is not the same as the assets M7 needs
  being present. Determine, and state separately:

    - what M7 actually requires from a materials library, sourced from the
      M7 requirements as recorded, not from your judgement
    - which of those requirements materials/ satisfies, by file
    - which it does not, by name, with the search extent that establishes
      absence
    - whether anything is present but unusable, and why — licence,
      corruption, format, encoding of the filename, anything

  If the residue is empty, say so plainly. If it is not, the residue IS the
  blocker and it should be re-scoped to exactly that, not left as a
  library-wide claim.

STEP B3 — CORRECT THE RECORD

  Amend palette_roadmap_continuation_state.json so that :272 and the
  MATERIALS_LIBRARY_ABSENT entry state what is true. Depending on B2 the
  entry is either WITHDRAWN with the reason, or RE-SCOPED to the named
  residue with its kind reconsidered — an EXTERNAL blocker that turns out to
  be satisfiable from inside the working copy is not EXTERNAL.

  Follow whatever authorization route this file's amendments actually require.
  READ THE ROUTE BEFORE CHOOSING IT. If it needs owner authorization, STOP
  and report with the exact text you would land — do not assume the D5c
  authorization extends to this, because it does not.

STEP B4 — WHY IT SURVIVED, IN THREE SENTENCES

  A false blocker sat in the roadmap state and gated a milestone, while a
  document at the repository root disproved it and the two were never
  compared. Say in no more than three sentences what mechanical control would
  have caught this, and whether that control exists anywhere in the programme.

  Do not build the control. Do not open a defect for it unless B4's answer is
  that no such control exists anywhere, in which case one honest OPEN entry
  is warranted.

DO NOT
  - change Moss Garden's hex, family, or any recorded shade value
  - widen SUBJECT_WINDOW, re-commission any rig, or bypass a refusal
  - edit the frozen builder
  - move any material identity
  - modify anything under materials/ — it is declared READ-ONLY
  - assume the D5c authorization covers ACT B
  - close D5

REPORT BACK
  - Moss Garden on both marbling axes, as authored, with the control
  - the ladder: both axes vs scene-linear peak, and the crossing value if
    there is one
  - whether the +0.05 desaturation hypothesis survived
  - the SUBJECT_WINDOW count with your peak definition, and whether my five
    or your eight is right
  - the new defect's wording
  - the four B1 answers with extents
  - the B2 residue, named, or "empty" with the extent that establishes it
  - what you did to the record, or what you would do and why you stopped
  - the three sentences from B4
  - anything in this brief that was wrong about the code
```

---

## WHAT COMES BACK TO YOU

**From ACT A**, one number: the scene-linear value at which marbling starts to
read. If it is above 0.35 then Moss Garden as authored can never show
structure, and you have a straight design choice — lighten the hero pan, or
change its family to something that survives at depth, or accept a hero pan
that is a flat deep olive and stop calling it marbled. All three are
defensible. None of them is available until the number exists.

**From ACT B**, most likely one fewer blocker. The materials library was never
absent; it is 28 GB sitting in the working copy, already inventoried by an
arc this programme built and then apparently forgot it had. If the B2 residue
comes back empty, the four standing blockers become three by correction rather
than by work — which is the cheapest possible way to lose one, and also a
small warning about what else in that file has never been re-checked.
